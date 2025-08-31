import hashlib
import hmac

from fastapi import FastAPI, Request, HTTPException

from settings import DISCORD_GUILD_ID, WEBHOOK_SECRET, bot

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
        guild = bot.get_guild(DISCORD_GUILD_ID)
        if not guild:
            return {"status": "error", "code": 500}

        d_user = guild.get_member_named(user)
        if d_user is None:
            print(f"Could not find user {user} in guild {guild.name}")
            print(f"{d_user}")
            return {"status": "error", "code": 404}
        try:
            await d_user.send(
                f"Bonjour {user}! Voici ton code pour t'inscrire sur le CTFd `{data['code']}`."
                "\nCopie ce code dans le champ ""Code d'inscription"" lors de la création de ton compte."
            )
        except Exception as e:
            print(f"Could not send DM to user {user}: {e}")
            return {"status": "error", "code": 403}


    return {"status": "ok"}