import hmac, hashlib, os

from fastapi import FastAPI, Request, Response, HTTPException

from .main import bot

WEBHOOK_SECRET = os.getenv("DISCORD_SHARED_KEY")

if not WEBHOOK_SECRET:
    raise ValueError("DISCORD_SHARED_KEY environment variable is not set")
app = FastAPI()


@app.post("/ctfd-webhook")
async def ctfd_webhook(request: Request):
    body = await request.body()
    received_sig = request.headers.get("X-Signature")
    if not received_sig:
        raise HTTPException(status_code=401, detail="Missing signature")

    expected_sig = hmac.new(
        WEBHOOK_SECRET.encode(),
        body,
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(received_sig, expected_sig):
        print("-=-=- Invalid signature received -=-=-")
        print(f"\t- Signature: {received_sig}")
        print(f"\t- Body: {body}")
        raise HTTPException(status_code=401, detail="Invalid signature")

    data = await request.json()
    if data["msg"] == "register":
        print("Received registration request")
        print(f"\t- Discord name: {data['discord_name']}")
        print(f"\t- Registration code: {data['code']}")

        # Send msg to registering user
        user = data["discord_name"]
        d_user = bot.get_guild(int(os.getenv("DISCORD_GUILD_ID"))).get_member_named(user)
        if not d_user:
            print(f"Could not find user {user} in guild")
            return {"status": "error", "code": 404}
        try:
            await d_user.send(
                f"Bonjour {user}! Voici ton code pour t'inscrire sur le CTFd `{data['code']}`."
                "Copie ce code dans le champ ""Code d'inscription"" lors de la création de ton compte."
            )
        except Exception as e:
            print(f"Could not send DM to user {user}: {e}")
            return {"status": "error", "code": 403}


    return {"status": "ok"}
