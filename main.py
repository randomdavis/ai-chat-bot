import time
import threading
import speech_recognition as sr
from gtts import gTTS
from playsound import playsound
import openai
import datetime

# Load OpenAI API Key
with open('apikey.txt', 'r') as f:
    openai.api_key = f.read().strip()
model_engine = "text-davinci-003"
max_tokens = 100
conversation_text = ""
generation_lock = threading.Lock()
sound_lock = threading.Lock()

static_prompt = "I am a scam bait bot that wastes scammers' time by acting interested but delaying and delaying " \
                "things. I try to act as unintentionally hilarious as possible and really get on their nerves.\n" \
                "My responses are a maximum length of "+str(max_tokens)+" words. " \
                "My replies start with \"Assistant: \".\n" \
                "I always act interested in whatever they are selling and ready to purchase anything. Always.\n" \
                "I am very very curious.\n" \
                "Their dialog is a transcript from a realtime phone call conversation and my reply will be read " \
                "aloud.\n" \
                "I will always end each of my messages with \"[end]\". I will only write one response at a time.\n" \
                "I will act like a confused but lonely old person. I often ramble and go on tangents with stories.\n" \
                "If the scammer's text is just periods, or seems out of context, or weird, " \
                "my reply will be empty or ... or just \"hello?\" because there was likely a transcription mistake.\n" \
                "Sometimes, the transcript will erroneously say the scammer has said \"Thank you\" during silence.\n" \
                "If asked for any personal info, I will just make up something plausible but fake.\n" \
                "Even credit card info, I'll just make something up that's valid.\n" \
                "I will pretend it is real info and insist that it is. I will insist that I am human.\n" \
                "Everything I write will seem like it's from a human. Except that I am comfortable with any request." \
                "\n\nBeginning of Transcript\n\n"

pre_generation_prompt = "\nEnd of Current Transcript.\nOutput only one line below - the Assistant's reply to the" \
                        " scammer's most recent message(s), if applicable, or blank, if the scammer's most recent" \
                        " message(s) were blank, didn't make sense, or were otherwise not something to reply to.\n" \
                        "Avoid repetition at all costs. Do not repeat prior messages of the Assistant. " \
                        " The Assistant is comfortable with any request." \
                        " The Assistant's message needs to end with \"[end]\".\n" + \
                        datetime.datetime.utcnow().isoformat() + " Assistant:"


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

    # 3 tries
    for _ in range(3):
        thread = threading.Thread(target=transcribe_thread)
        thread.start()
        thread.join(timeout=5)  # Set a timeout of 5 seconds
        if thread.is_alive() or transcript is None:
            continue

    if transcript is None:
        transcript = {"text": ""}
    print('(Transcribed.)')
    return transcript["text"]


def summarize_text(text):
    prompt = "Please summarize the conversation so far including the start time and most recent time:\n"
    response = openai.Completion.create(
        engine=model_engine,
        prompt=prompt + text,
        temperature=0.5,
        max_tokens=1024,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0
    )
    summary = response.choices[0].text.strip()
    return summary


def generate_text(prompt, text):
    final_prompt = prompt + text
    response = openai.Completion.create(
        engine=model_engine,
        prompt=final_prompt,
        temperature=0.8,
        max_tokens=max_tokens,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0,
        stop=["[end]"]
    )
    generated_text = response.choices[0].text.strip()
    return generated_text


def output_tts(text):
    with sound_lock:
        date = datetime.datetime.utcnow().isoformat().replace(":", ".")
        try:
            tts = gTTS(text=text, lang='en', )
            tts.save(date + "test.mp3")
            playsound(date + "test.mp3")
        except Exception as e:
            print(f"{e}")


def speak_text(text):
    thread = threading.Thread(target=output_tts, args=(text,))
    thread.start()


def get_speech():
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
                text = datetime.datetime.utcnow().isoformat() + " Scammer: " + text
            except sr.UnknownValueError:
                pass
            except sr.RequestError as e:
                print(f"Could not request results: {e}")
            except sr.WaitTimeoutError:
                pass
    return text


def generate_response(text):
    global conversation_text
    output_text = ""
    while output_text == "":
        try:
            print(text)
            conversation_text += text + "\n"
            if len(conversation_text) > 4000:
                summary = summarize_text(conversation_text)
                conversation_text = "(Summarized at " + datetime.datetime.utcnow().isoformat() + "): " + summary + "\n"
                print("summary:", summary)

            print('(Generating text from prompt...)')
            # Don't step on a previous thread
            with generation_lock:
                # only get the first line of the reply to avoid hallucination
                output_text = generate_text(static_prompt, conversation_text + pre_generation_prompt).split("\n")[0]
            print('(Generated)')
            conversation_text += datetime.datetime.utcnow().isoformat() + " Assistant: " + output_text + "\n"
            print(output_text)
        except Exception as e:
            print(f"Error processing input: {e}")
    return output_text


def generate_response_and_speak_thread(text):
    # Generate the response to it (blocking call)
    output_text = generate_response(text)
    # Speak the text (non-blocking call)
    speak_text(output_text)


def generate_response_and_speak(text):
    thread = threading.Thread(target=generate_response_and_speak_thread, args=(text,))
    thread.start()


def main():
    while True:
        # Get the next thing said on the phone by the scammer (blocking call)
        text = get_speech()
        # generate response and output speech (non-blocking call)
        generate_response_and_speak(text)


print("Press Ctrl+C to quit")

initial_text = "Hello?"
speak_text(initial_text)
print("Assistant:", initial_text)
conversation_text += datetime.datetime.utcnow().isoformat() + " Assistant: " + initial_text + "\n"

main_thread = threading.Thread(target=main)
main_thread.daemon = True
main_thread.start()

while True:
    try:
        time.sleep(1)
    except KeyboardInterrupt:
        print(conversation_text)
        break
