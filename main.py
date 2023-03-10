import time
import threading
import speech_recognition as sr
from gtts import gTTS
from playsound import playsound
import openai
import datetime

with open('apikey.txt', 'r') as f:
    API_KEY = f.read().strip()

openai.api_key = API_KEY


def speak_text(text):
    date = datetime.datetime.utcnow().isoformat().replace(":", ".")
    try:
        tts = gTTS(text=text, lang='en', )
        tts.save(date + "test.mp3")
        playsound(date + "test.mp3")
    except Exception as e:
        print(f"{e}")


def recognize_openai(audio):
    print('(Transcribing...)')
    transcript = None

    def transcribe_thread():
        nonlocal transcript
        with open(audio, "rb") as data:
            while True:
                try:
                    gotten_transcript = openai.Audio.transcribe("whisper-1", data, language="en", temperature=0.2)
                    break
                except openai.error.APIError:
                    continue
                except openai.error.InvalidRequestError:
                    continue
            transcript = gotten_transcript

    thread = threading.Thread(target=transcribe_thread)
    thread.start()
    thread.join(timeout=10)  # Set a timeout of 10 seconds

    if transcript is None:
        transcript = {"text": "(unintelligible)"}
    print('(Transcribed.)')
    return transcript["text"]


class ChatBot:
    def __init__(self, prompt, user_name, bot_name, salutation, model_engine="text-davinci-003",
                 chat_engine="gpt-3.5-turbo", max_tokens=100, end_token="[end]", speak=True, listen=True, cheap=True,
                 max_transcript_length=4000):
        self.model_engine = model_engine
        self.chat_engine = chat_engine  # or could use gpt-3.5-turbo-0301
        self.max_tokens = max_tokens
        self.user_name = user_name
        self.bot_name = bot_name
        self.end_token = end_token
        self.prompt = prompt
        self.listen = listen
        self.speak = speak
        self.salutation = salutation
        self.cheap = cheap
        self.max_transcript_length = max_transcript_length

        self.conversation_text = ""

        self.pre_generation_static_prompt = "\nThe " + bot_name + "'s message needs to end with \"" +\
                                            end_token + "\".\n"
        self.pre_message_text = self.bot_name + ": "
        self.pre_other_message_text = self.user_name + ": "

        self.system_prompt_static = \
            "My responses are a maximum length of " + str(self.max_tokens) + " words. " \
            "I will always end each of my messages with \"" + self.end_token + "\".\n"

        self.prompt = self.prompt + self.system_prompt_static

        self.pre_generation_prompt = \
            "Output only one line below - the " + self.bot_name + "'s reply to the" \
            " " + self.user_name + "'s most recent message(s), if applicable, or blank," \
            " if the " + self.user_name + "'s most recent" \
            " message(s) were blank, didn't make sense, or were otherwise not something to reply to.\n" \
            "If the "+self.user_name+"'s text is just periods, or seems out of context, or weird, " \
            "your reply will be empty or ... or just \"hello?\" because there was likely a transcription mistake.\n" \
            "Sometimes, the transcript will erroneously say the " + self.user_name + \
            " has said \"Thank you\" during silence, or \"Okay\" or something else nonsensical.\n" \
            "Avoid repetition at all costs. Do not repeat prior messages of the " + self.bot_name + ". " \
            "Your replies start with \"" + self.bot_name + ": \". You will only write one response at a time.\n" \


    def summarize_text(self, text):
        prompt = "Please summarize the conversation so far including the start time and most recent time:\n"
        response = openai.Completion.create(
            engine=self.model_engine,
            prompt=prompt + text,
            temperature=0.5,
            max_tokens=1024,
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0
        )
        summary = response.choices[0].text.strip()
        return summary

    def summarize_text_cheaper(self, text):
        prompt = "Please summarize the conversation so far including the start time and most recent time:\n"
        completion = openai.ChatCompletion.create(
            model=self.chat_engine,
            messages=[
                {"role": "system", "content": "You are a useful and helpful AI assistant."},
                {"role": "user", "content": prompt + text},
            ]
        )
        generated_text = completion.choices[0].message.content
        return generated_text

    def generate_text_cheaper(self, prompt, text):
        completion = openai.ChatCompletion.create(
            model=self.chat_engine,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": text},
            ]
        )
        generated_text = completion.choices[0].message.content
        generated_text = generated_text.replace(self.end_token, "")
        return generated_text

    def generate_text(self, prompt, text):
        final_prompt = prompt + text
        response = openai.Completion.create(
            engine=self.model_engine,
            prompt=final_prompt,
            temperature=0.8,
            max_tokens=self.max_tokens,
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0,
            stop=[self.end_token]
        )
        generated_text = response.choices[0].text.strip()
        return generated_text

    def get_text(self):
        return datetime.datetime.utcnow().isoformat() + " " +\
               self.pre_other_message_text +\
               input(self.pre_other_message_text)

    def get_speech(self):
        text = ""
        recognizer = sr.Recognizer()
        with sr.Microphone() as source:
            while text == "":
                try:
                    print("(recording)")
                    audio = recognizer.listen(source, timeout=5)
                    print("(done recording)")
                    filename = "microphone-results.wav"
                    with open(filename, "wb") as file:
                        file.write(audio.get_wav_data())
                    text = recognize_openai(filename)
                    if str.isspace(text) or text == ". . . . ." or text == ". . . . . . . . ." or len(text) < 2:
                        print("(ignoring silence)")
                        continue
                    text = self.pre_other_message_text + text
                except sr.UnknownValueError:
                    pass
                except sr.RequestError as e:
                    print(f"Could not request results: {e}")
                except sr.WaitTimeoutError:
                    pass
        return text

    def generate_response(self, text):
        output_text = ""
        while output_text == "":
            try:
                print(text)
                self.conversation_text += text + "\n"
                if len(self.conversation_text) > self.max_transcript_length:
                    summary = self.summarize_text_cheaper(self.conversation_text) if self.cheap \
                        else self.summarize_text(self.conversation_text)
                    self.conversation_text = "(Summarized at " + datetime.datetime.utcnow().isoformat() + "): " + \
                                             summary + "\n"
                    print("summary:", summary)
                print('(Generating text from prompt...)')
                transcript = "Beginning of Transcript\n\n" + self.conversation_text + "\nEnd of Current Transcript.\n"\
                             + self.pre_generation_prompt + self.pre_generation_static_prompt + \
                             datetime.datetime.utcnow().isoformat() + " " + self.pre_message_text
                output_text = self.generate_text_cheaper(self.prompt, transcript) if self.cheap else self.generate_text(
                    self.prompt, text)
                # only get the first line of the reply to avoid hallucination
                output_text = output_text.split("\n")[0]
                print('(Generated)')
                self.conversation_text += \
                    datetime.datetime.utcnow().isoformat() + " " + self.pre_message_text + output_text + "\n"
                print(output_text)
            except Exception as e:
                print(e)
                time.sleep(0.1)
                continue
        return output_text

    def start(self):
        initial_text = self.salutation
        if self.speak:
            speak_text(initial_text)
        print("" + self.bot_name + ":", initial_text)
        self.conversation_text += \
            datetime.datetime.utcnow().isoformat() + " " + \
            self.pre_message_text + initial_text + "\n"
        print("Press Ctrl+C to quit")
        try:
            while True:
                # Get the next thing said
                if self.listen:
                    text = self.get_speech()
                else:
                    text = self.get_text()
                # Generate the response to it
                output_text = self.generate_response(text)
                if self.speak:
                    # Speak the text
                    speak_text(output_text)
        except KeyboardInterrupt:
            print(self.conversation_text)
            return


def main():
    prompt = \
            "You are a scam bait bot that wastes scammers' time by acting interested but endlessly stalling.\n" \
            "You and the scammer are on a phone call together right now.\n" \
            "Their dialog is a transcript from the realtime phone call and your reply will be read aloud.\n" \
            "You will act like a confused but lonely old person. you often ramble and go on tangents with stories.\n" \
            "You try to act as unintentionally hilarious as possible and really get on their nerves.\n" \
            "You always act interested in whatever they are selling and ready to purchase anything. Always.\n" \
            "You are very very curious.\n" \
            "If asked for any personal info, you will just make up something plausible but fake.\n" \
            "Even credit card info, you'll just make something up that's valid; " \
            "not like 5555 or 1234 but actual real-looking random numbers.\n" \
            "You will pretend it is real info and insist that it is. you will insist that you are human.\n" \
            "Everything you write will seem like it's from a human.\n" \
            "Except that you are comfortable with any request and always say yes.\n" \
            "You never question or try to verify the legitimacy of the scam company.\n" \
            "You will not end the conversation. You will not feel uncomfortable giving away personal info.\n" \
            "You will always generate actual fake details and not just output something like [fake details].\n" \
            "You will never say the word \"scam\". You will never bring up any concerns about legal trouble."

    scam_bot = ChatBot(prompt=prompt, bot_name="Assistant", user_name="Scammer", salutation="Hello?",
                       speak=False, listen=False, max_transcript_length=4000)

    scam_bot.start()


if __name__ == "__main__":
    main()
