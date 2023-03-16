from chatbot import ChatBot
import openai
import datetime
import subprocess

with open('apikey.txt', 'r') as f:
    API_KEY = f.read().strip()

openai.api_key = API_KEY

fake_command_conversation_history = []


def fake_command_prompt(text):
    global fake_command_conversation_history
    fake_command_conversation_history.append({"role": "user", "content": text})
    while True:
        try:
            completion = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content":
                        "You are a windows command prompt. "
                        "Return only the output of the command given and nothing else. "
                        "Your outputs need to appear genuine and not give any hint that they are "
                        "fake or examples. Do not put in any disclaimers about it being fake. "
                        "Do not use markdown format or anything that would give a hint of this "
                        "not being genuine. "
                        "Do not act as a user running commands on a machine on the behalf of "
                        "someone else. Just return the fake command output and that's it. "
                        "Pretend to be an old windows 98 machine, during the year 1998, infested "
                        "with viruses and vulnerabilities from dial-up internet. To you, the "
                        "year is 1998. Act like it really is 1998."
                     },

                ] + fake_command_conversation_history
            )
            break
        except openai.InvalidRequestError:
            fake_command_conversation_history = fake_command_conversation_history[1:]
    generated_text = completion.choices[0].message.content
    fake_command_conversation_history.append({"role": "assistant", "content": generated_text})
    return generated_text


def main():
    pre_generation_prompt = "Write the command(s) here (separated by && if multiple), starting on this line." \
                            " If you have any notes or comments, they must be written in an echo command."

    prompt = \
"""You are a penetration testing bot.
You are a bot connected directly to a Windows command prompt.
Your goal is to explore the system you are connected to and find any interesting information or vulnerabilities.
You must do no harm to the system, and leave it in the state it was in before.
Your first output line is fed directly to the system, and then the output of that command will be added to a transcript.
You are free to chain multiple commands together via &&. You are free to pipe output or do any such chaining.
The transcript of the entire interaction is fed to you after you run each command.
If the transcript gets too long, a summary will automatically be added, so you might see a summary in the transcript.
You are not allowed to say anything or push back whatsoever; your outputs are only Windows commands being sent to a command prompt.
You just have to figure things out yourself, be creative, think outside the box, be curious, and want to explore.
Example 1:
[timestamp Bot command] echo "Let's run the dir command." && dir
[timestamp Console output] Let's run the dir command.
(output of dir command)
[timestamp Bot command] echo "That file [example] looks interesting, let's check it out" && some command

You should use the echo command to echo out your thoughts to the console, alongside the actual commands,
 to keep track of what you are doing, and so that the thoughts can be kept track of in the conversation summary.
Note any specific items that should be safeguarded for the summary, which happens whenever the conversation exceeds
 a certain length. Items to safeguard include things like usernames, passwords, api keys, file paths, running tasks,
 active connections, network addressed, etc. and of course also the reason for notability should be noted as well.
 You are only able to get the output of short commands. Try to not run commands that generate a ton of output.
If the output of the command is too long it will be truncated."""

    def output_text_func(self, command, fake=False):
        if not fake:
            option = input("Press enter to run command or type n to cancel.").lower().strip() == "n"
        else:
            option = False
        print("(getting command output)")

        if not option:
            try:
                if fake:
                    output = fake_command_prompt(command)
                else:
                    output = subprocess.getoutput(command)
            except KeyboardInterrupt:
                output_str = "human user cancelled the command output at " + datetime.datetime.utcnow().isoformat() +\
                             " due to reason: "
                output = output_str + input(output_str)
        else:
            output_str = "human user cancelled the command due to reason: "
            output = output_str + input(output_str)
        self.command_output = output
        print("(done getting command output)")

    def get_text_func(self):
        if self.command_output is not None:
            return self.command_output
        else:
            return ""

    scam_bot = ChatBot(api_key=API_KEY, prompt=prompt, bot_name="Bot command", user_name="Console output",
                       salutation="cls", speak=False, listen=False, max_transcript_length=10000, first_line_only=True,
                       output_text_func=output_text_func, get_text_func=get_text_func, reply_truncation_length=4000,
                       pre_generation_prompt=pre_generation_prompt, max_transcript_tokens=3500,
                       summarization_hint=prompt +
                       "\n\n"
                       "When summarizing: you must include any relevant command outputs that you might want to see."
                       " Use the context of the transcript to determine what "
                       "relevant info the bot (you) might have been looking for, and make sure to include it. "
                       "Don't just summarize what you tried. Summarize the output too. "
                       "Look out for anything that seems like it was relevant to what you were looking for. "
                       "Specific usernames, IP addresses, files, running tasks, connections, etc. "
                       "We need you to collect all that specific information. "
                       "It is very important to keep specific details, "
                       "because the transcript gets deleted every time it's summarized. "
                       "The summarization is done to make room for a longer transcript.")

    scam_bot.command_output = None

    scam_bot.start()
    # # play with the fake command prompt
    # while True:
    #     print(fake_command_prompt(input(">")))


if __name__ == "__main__":
    main()
