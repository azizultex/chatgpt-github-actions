# Automated Code Review using the ChatGPT language model

## Import statements
import argparse
import openai
import os
import requests
from github import Github

## Adding command-line arguments
parser = argparse.ArgumentParser()
parser.add_argument('--openai_api_key', help='Your OpenAI API Key')
parser.add_argument('--github_token', help='Your Github Token')
parser.add_argument('--github_pr_id', help='Your Github PR ID')
parser.add_argument('--openai_engine', default="text-davinci-002", help='GPT-3 model to use. Options: text-davinci-002, text-babbage-001, text-curie-001, text-ada-001')
parser.add_argument('--openai_temperature', default=0.5, help='Sampling temperature to use. Higher values means the model will take more risks. Recommended: 0.5')
parser.add_argument('--openai_max_tokens', default=2048, help='The maximum number of tokens to generate in the completion.')
parser.add_argument('--mode', default="files", help='PR interpretation form. Options: files, patch')
args = parser.parse_args()

## Authenticating with the OpenAI API
openai.api_key = args.openai_api_key

## Authenticating with the Github API
g = Github(args.github_token)


def files():
    repo = g.get_repo(os.getenv('GITHUB_REPOSITORY'))

    pull_request = repo.get_pull(int(args.github_pr_id))

    ## Loop through the commits in the pull request
    commits = pull_request.get_commits()
    for commit in commits:
        # Getting the modified files in the commit
        files = commit.files

        for file in files:
            try:
                # Getting the file name and content
                file_name = file.filename
                content = repo.get_contents(file_name, ref=commit.sha).decoded_content

                # Sending the code to ChatGPT
                response = openai.ChatCompletion.create(
                    model=args.openai_engine,
                    messages=[
                        {
                            "role" : "user",
                            "content" : prompt_text(content)
                        }
                    ],
                    temperature=float(args.openai_temperature),
                    max_tokens=int(args.openai_max_tokens)
                )

                # Adding a comment to the pull request with ChatGPT's response
                response_text = response['choices'][0]['message']['content'];

                pull_request.create_issue_comment(
                    f"ChatGPT's response about ``{file_name}``:\n {response_text}")

                if response_text.strip().lower() != "looks good!":
                    exit(1)

            except Exception as e:
                error_message = str(e)
                pull_request.create_issue_comment(f"ChatGPT encountered an error while processing `{file.filename}`: {error_message}")


def patch():
    repo = g.get_repo(os.getenv('GITHUB_REPOSITORY'))
    pull_request = repo.get_pull(int(args.github_pr_id))

    content = get_content_patch()

    if len(content) == 0:
        pull_request.create_issue_comment(f"Patch file does not contain any changes")
        return

    parsed_text = content.split("diff")

    print("parsed_text", parsed_text)

    for diff_text in parsed_text:

        print("diff_text", diff_text)
        
        if len(diff_text) == 0:
            continue

        try:
            file_name = diff_text.split("b/")[1].splitlines()[0]
            print("file_name", file_name)

            # Extract file extension
            file_extension = os.path.splitext(file_name)[1]

            # Filter file type
            if file_extension not in ['.php', '.js']:
                continue

            response = openai.ChatCompletion.create(
                model=args.openai_engine,
                messages=[
                            {
                                "role" : "user",
                                "content" : prompt_text(diff_text)
                            }
                        ],
                temperature=float(args.openai_temperature),
                max_tokens=int(args.openai_max_tokens)
            )

            response_text = response['choices'][0]['message']['content'];

            print("response_text", response_text)

            pull_request.create_issue_comment(
                f"ChatGPT's response about ``{file_name}``:\n {response_text}")

            if response_text.strip().lower() != "looks good!":
                exit(1)

        except Exception as e:
            error_message = str(e)
            pull_request.create_issue_comment(f"ChatGPT was unable to process the response about {file_name}")


# Construct the prompt
def prompt_text(code: str) -> str:
    prompt = f"""
    Act as an expert php, javascript developer. Please thoroughly review the provided WordPress theme or plugin code from Github pull request based on the following criteria:
    1. **Best Practices**: Ensure the code adheres to WordPress Codex standards.
    2. **Security**: Look for potential vulnerabilities, especially in data handling. Ensure proper sanitization methods are used.
    3. **Readability**: Suggest improvements to make the code more readable and maintainable. Offer better names for variables, functions, and classes, if can be improved.
    4. **Optimization**: Analyze the time and space complexity, and recommend ways to enhance performance.
    After the analysis, please point out the exact issues in the code with line number in a block and provide possible solutions. Don't explain anything if codes looks fine. Just response "Looks good!" if no serious issues found.

    CODE STARTS HERE:

    {code}
    """
    return prompt

def get_content_patch():
    url = f"https://api.github.com/repos/{os.getenv('GITHUB_REPOSITORY')}/pulls/{args.github_pr_id}"

    headers = {
        'Authorization': f"token {args.github_token}",
        'Accept': 'application/vnd.github.v3.diff'
    }

    response = requests.request("GET", url, headers=headers)


    if response.status_code != 200:
        raise Exception(response.text)

    return response.text


if (args.mode == "files"):
    files()

if (args.mode == "patch"):
    patch()
