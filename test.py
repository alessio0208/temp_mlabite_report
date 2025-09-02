import os
import requests
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()
url = os.environ['LLM_FACTORY_URL']

def execute_prompt(llm, prompt):
    payload = {
    "model": llm, 
    "prompt": prompt,
    }
    
    response = requests.post(f"{url}/execute_prompt", json=payload)
    status = response.status_code
    
    if status == 200:
        try:
            response = response.json().get("response")
        except ValueError:
            response = response.text.strip()   
    else:
        raise RuntimeError(
            f"Status: {status}"
        )
        
    return response

if __name__ == "__main__":
    response = execute_prompt(llm="BILOpenAI", prompt="tell me a fun fact about Luxembourg")
    print(response)