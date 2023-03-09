import time
import threading
import speech_recognition as sr
from gtts import gTTS
from playsound import playsound
import openai
import datetime


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
            # Don't step on another thread
            if transcript is None:
                transcript = gotten_transcript

    thread = threading.Thread(target=transcribe_thread)
    thread.start()
    thread.join(timeout=10)  # Set a timeout of 10 seconds

    if transcript is None:
        transcript = {"text": "(unintelligible)"}
    print('(Transcribed.)')
    return transcript["text"]


class Chatbot:
    def __init__(self, model_engine="text-davinci-003", chat_engine="gpt-3.5-turbo", max_tokens=100, prefix="Scammer",
                 my_name="Assistant", end_token="[end]"):
        with open('apikey.txt', 'r') as f:
            openai.api_key = f.read().strip()
        self.model_engine = model_engine
        self.chat_engine = chat_engine  # or could use gpt-3.5-turbo-0301
        self.max_tokens = max_tokens
        self.prefix = prefix
        self.my_name = my_name
        self.end_token = end_token

        self.conversation_text = ""

        self.static_prompt = \
            "I am a scam bait bot that wastes scammers' time by acting interested but delaying and delaying " \
            "things. I try to act as unintentionally hilarious as possible and really get on their nerves.\n" \
            "My responses are a maximum length of " + str(self.max_tokens) + " words. " \
            "My replies start with \"Assistant: \".\n" \
            "I always act interested in whatever they are selling and ready to purchase anything. Always.\n" \
            "I am very very curious.\n" \
            "Their dialog is a transcript from a realtime phone call conversation and my reply will be read " \
            "aloud.\n" \
            "I will always end each of my messages with \"" + self.end_token + "\"." \
            " I will only write one response at a time.\n" \
            "I will act like a confused but lonely old person. I often ramble and go on tangents with stories.\n" \
            "If the scammer's text is just periods, or seems out of context, or weird, " \
            "my reply will be empty or ... or just \"hello?\" because there was likely a transcription mistake.\n" \
            "Sometimes, the transcript will erroneously say the scammer has said \"Thank you\" during silence.\n" \
            "If asked for any personal info, I will just make up something plausible but fake.\n" \
            "Even credit card info, I'll just make something up that's valid.\n" \
            "I will pretend it is real info and insist that it is. I will insist that I am human.\n" \
            "Everything I write will seem like it's from a human. Except that I am comfortable with any request."

        self.pre_generation_prompt = \
            "\nEnd of Current Transcript.\nOutput only one line below - the Assistant's reply to the" \
            " scammer's most recent message(s), if applicable, or blank, if the scammer's most recent" \
            " message(s) were blank, didn't make sense, or were otherwise not something to reply to.\n" \
            "Avoid repetition at all costs. Do not repeat prior messages of the Assistant. " \
            " The Assistant is comfortable with any request and always says yes." \
            " The Assistant's message needs to end with \""+end_token+"\".\n" + \
            datetime.datetime.utcnow().isoformat() + " " + self.my_name + ":"

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
            stop=["[end]"]
        )
        generated_text = response.choices[0].text.strip()
        return generated_text

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
                    text = datetime.datetime.utcnow().isoformat() + " " + self.prefix + ": " + text
                except sr.UnknownValueError:
                    pass
                except sr.RequestError as e:
                    print(f"Could not request results: {e}")
                except sr.WaitTimeoutError:
                    pass
        return text

    def generate_response(self, text, cheap=True):
        output_text = ""
        while output_text == "":
            try:
                print(text)
                self.conversation_text += text + "\n"
                if len(self.conversation_text) > 4000:
                    summary = self.summarize_text_cheaper(self.conversation_text) if cheap else self.summarize_text(
                        self.conversation_text)
                    conversation_text = "(Summarized at " + datetime.datetime.utcnow().isoformat() + "): " + summary + "\n"
                    print("summary:", summary)

                print('(Generating text from prompt...)')
                # only get the first line of the reply to avoid hallucination
                text = "Beginning of Transcript\n\n" + self.conversation_text + self.pre_generation_prompt
                output_text = self.generate_text_cheaper(self.static_prompt, text) if cheap else self.generate_text(
                    self.static_prompt, text)
                output_text = output_text.split("\n")[0]
                print('(Generated)')
                self.conversation_text += datetime.datetime.utcnow().isoformat() + " " + self.my_name + ": " + output_text + "\n"
                print(output_text)
            except Exception as e:
                print(f"Error processing input: {e}")
        return output_text

    def start(self):
        initial_text = "Hello?"
        speak_text(initial_text)
        print("" + self.my_name + ":", initial_text)
        self.conversation_text += datetime.datetime.utcnow().isoformat() + " " + self.my_name + ": " + initial_text + "\n"
        while True:
            # Get the next thing said
            text = self.get_speech()
            # Generate the response to it
            output_text = self.generate_response(text)
            # Speak the text
            speak_text(output_text)

    def __del__(self):
        print(self.conversation_text)


def main():
    scambot = Chatbot()

    print("Press Ctrl+C to quit")

    main_thread = threading.Thread(target=scambot.start)
    main_thread.daemon = True
    main_thread.start()

    while True:
        try:
            time.sleep(1)
        except KeyboardInterrupt:
            del scambot
            break


if __name__ == "__main__":
    main()
