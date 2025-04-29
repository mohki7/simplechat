import json
import os
import urllib.request
import urllib.error
import ssl
import re

# ────────────────────────────────────────────
# 0.  環境変数
API_ENDPOINT = os.environ.get(
    "API_ENDPOINT",
    "https://6470-35-229-170-246.ngrok-free.app"
)

def extract_region_from_arn(arn: str) -> str:
    m = re.search(r"arn:aws:lambda:([^:]+):", arn)
    return m.group(1) if m else "us-east-1"

# ────────────────────────────────────────────
def lambda_handler(event, context):
    """Front → (API Gateway) → Lambda という構成を想定。
    event = {
        "body": "{\"message\": \"こんにちは\", \"conversationHistory\": [...] }",
        ...
    }
    """
    try:
        print("▶ Received event:", json.dumps(event)[:1000])

        body     = json.loads(event["body"])
        message  = body["message"]
        history  = body.get("conversationHistory", [])

        prompt_parts = [f"{m['role']}: {m['content']}" for m in history]
        prompt_parts.append(f"user: {message}")
        prompt = "\n".join(prompt_parts)

        payload = {
            "prompt": prompt,
            "max_new_tokens": 256
        }
        data_bytes = json.dumps(payload).encode("utf-8")

        req = urllib.request.Request(
            API_ENDPOINT,
            data=data_bytes,
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        with urllib.request.urlopen(req, timeout=30) as resp:
            resp_body = resp.read().decode("utf-8")

        api_json = json.loads(resp_body)
        print("▶ FastAPI response:", api_json)

        if "generated_text" not in api_json:
            raise ValueError("generated_text not found in API response")

        assistant_response = api_json["generated_text"]

        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": assistant_response})

        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
                "Access-Control-Allow-Methods": "OPTIONS,POST"
            },
            "body": json.dumps({
                "success": True,
                "response": assistant_response,
                "conversationHistory": history
            })
        }

    # ── 失敗したらここ
    except (urllib.error.URLError, urllib.error.HTTPError) as url_err:
        err_msg = f"FastAPI call failed: {url_err}"
    except Exception as e:
        err_msg = str(e)

    print("❌ Error:", err_msg)
    return {
        "statusCode": 500,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
            "Access-Control-Allow-Methods": "OPTIONS,POST"
        },
        "body": json.dumps({
            "success": False,
            "error": err_msg
        })
    }
