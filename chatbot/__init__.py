import time
import threading
import speech_recognition as sr
from gtts import gTTS
from playsound import playsound
import openai
import datetime


API_KEY_SET = False


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
    def __init__(self, api_key, prompt, user_name, bot_name, salutation, pre_generation_prompt=None, model_engine="text-davinci-003",
                 chat_engine="gpt-3.5-turbo", max_tokens=100, end_token=None, speak=True, listen=True, cheap=True,
                 max_transcript_length=4000, first_line_only=True, output_text_func=None, get_text_func=None,
                 max_transcript_tokens=3000, summarization_hint="", reply_truncation_length=1000):
        global API_KEY_SET
        if not API_KEY_SET:
            openai.api_key = api_key
            API_KEY_SET = True
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
        self.max_transcript_tokens = max_transcript_tokens
        self.first_line_only = first_line_only
        self.pre_generation_prompt = pre_generation_prompt
        self.output_text_func = output_text_func
        self.get_text_func = get_text_func
        self.summarization_hint = summarization_hint
        self.reply_truncation_length = reply_truncation_length

        self.total_tokens = 0
        self.conversation_text = ""
        self.pre_generation_static_prompt = ""
        self.pre_message_text = self.bot_name + "] "
        self.pre_other_message_text = self.user_name + "] "

        if self.max_tokens is not None:
            self.system_prompt_static = "Your responses are a maximum length of " + str(self.max_tokens) + " words. "
        else:
            self.system_prompt_static = ""
        if self.end_token is not None:
            self.pre_generation_static_prompt += "\nThe " + self.bot_name + "'s message needs to end with \"" + self.end_token + "\".\n"
            self.system_prompt_static += "I will always end each of my messages with \"" + self.end_token + "\".\n"

        self.prompt = self.prompt + self.system_prompt_static

        if pre_generation_prompt is None:
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
                "Your replies start with \"" + self.bot_name + ": \". You will only write one response at a time.\n"

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
        prompt = "\n\nPlease summarize the conversation so far including the start time and most recent time. " \
                 "Make sure to include as much helpful and detailed info as possible on the content of the transcript:\n"
        completion = openai.ChatCompletion.create(
            model=self.chat_engine,
            messages=[
                {"role": "system", "content": "You are a text-summarizing bot. You always include as much relevant info as possible when summarizing. " + self.summarization_hint},
                {"role": "user", "content": text + prompt},
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
        self.total_tokens = completion.usage.total_tokens
        generated_text = completion.choices[0].message.content
        if self.end_token is not None:
            generated_text = generated_text.replace(self.end_token, "")
        return generated_text

    def generate_text(self, prompt, text):
        final_prompt = prompt + text

        response = openai.Completion.create(
            engine=self.model_engine,
            prompt=final_prompt,
            temperature=0.8,
            max_tokens=self.max_tokens if self.max_tokens is not None else 4000,
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0,
            stop=[self.end_token] if self.end_token is not None else []
        )
        generated_text = response.choices[0].text.strip()
        return generated_text

    def get_text(self):
        prepend = "[" + datetime.datetime.utcnow().isoformat() + " " + self.pre_other_message_text
        if self.get_text_func is None:
            return input(prepend)
        else:
            print(prepend, end="")
            return self.get_text_func(self)

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
                    text = "[" + self.pre_other_message_text + text
                except sr.UnknownValueError:
                    pass
                except sr.RequestError as e:
                    print(f"Could not request results: {e}")
                except sr.WaitTimeoutError:
                    pass
        return text

    def summarize_transcript(self, force=False):
        if force or (len(self.conversation_text) > self.max_transcript_length) or self.total_tokens > self.max_transcript_tokens:
            summary = self.summarize_text_cheaper(self.conversation_text) if self.cheap \
                else self.summarize_text(self.conversation_text)
            self.conversation_text = "(Summarized at " + datetime.datetime.utcnow().isoformat() + "): " + \
                                     summary + "\n"
            print("summary:", summary)

    def generate_response(self, text, first_line_only=True):
        output_text = ""
        old_conversation_text = self.conversation_text
        print(text)
        did_truncate_text = False
        did_truncate_transcript = False
        self.conversation_text += text + "\n"
        print('(Generating text from prompt...)')
        while output_text == "":
            try:
                transcript = "Beginning of Transcript\n\n" + self.conversation_text + "\nEnd of Current Transcript.\n" \
                             + self.pre_generation_static_prompt + self.pre_generation_prompt \
                             + "[" + datetime.datetime.utcnow().isoformat() + " " + self.pre_message_text
                output_text = self.generate_text_cheaper(self.prompt, transcript) if self.cheap else self.generate_text(
                    self.prompt, transcript)
                # only get the first line of the reply to avoid hallucination
                if first_line_only:
                    output_text = output_text.split("\n")[0]
                self.conversation_text += "[" + \
                                          datetime.datetime.utcnow().isoformat() + " " + self.pre_message_text +\
                                          output_text + "\n"
                self.summarize_transcript()
                print('(Generated)')
                print(output_text)

            except openai.InvalidRequestError as e:
                if "This model's maximum context length is" in e.user_message:
                    self.conversation_text = old_conversation_text
                    self.conversation_text = old_conversation_text + "[" + \
                        datetime.datetime.utcnow().isoformat() + " " + self.pre_message_text
                    if not did_truncate_text:
                        truncated_text = self.conversation_text[:self.reply_truncation_length] + \
                                         "(" + str(len(self.conversation_text)) + " characters total, " + \
                                         str(self.reply_truncation_length) + " shown)"
                        text = truncated_text + "...[truncated because output was too long]"
                        self.conversation_text += text + "\n"
                        did_truncate_text = True
                    else:
                        try:
                            if not did_truncate_transcript:
                                self.summarize_transcript(force=True)
                        except openai.InvalidRequestError as ee:
                            if "This model's maximum context length is" in ee.user_message:
                                if not did_truncate_transcript:
                                    # conversation is too long to summarize. truncate it.
                                    did_truncate_transcript = True
                                    truncated_text = self.conversation_text[:self.max_transcript_length] + \
                                        "("+str(len(self.conversation_text))+" characters total, " + \
                                        str(self.max_transcript_length)+" shown)"
                                    self.conversation_text = truncated_text
                                else:
                                    transcript_removed_text = "(transcript removed)"
                                    if self.conversation_text != transcript_removed_text:
                                        # truncating still made it not summarize. Getting rid of it.
                                        self.conversation_text = "(transcript removed)"
                                    else:
                                        # things are seriously broken, the output is too long despite us trying everything
                                        raise RuntimeError("Input too long for API. Giving up.\n"
                                                           "text:" + text +
                                                           "\nold_conversation_text:" + old_conversation_text +
                                                           "\noutput_text:" + output_text)
                time.sleep(1)
                continue
            except Exception as e:
                print(e)
                time.sleep(5)
                continue

        return output_text

    def start(self):
        initial_text = self.salutation
        if self.speak:
            speak_text(initial_text)
        print("" + self.bot_name + ":", initial_text)
        self.conversation_text += "[" + \
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
                output_text = self.generate_response(text, self.first_line_only)
                if self.output_text_func is not None:
                    self.output_text_func(self, output_text)
                if self.speak:
                    # Speak the text
                    speak_text(output_text)
        except KeyboardInterrupt:
            print(self.conversation_text)
            return
