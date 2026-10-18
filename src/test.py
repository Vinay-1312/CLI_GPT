import httpx, keyring

api_key = keyring.get_password("groq_key", "default")

response = httpx.get(
    "https://api.groq.com/openai/v1/models",
    headers={"Authorization": f"Bearer {api_key}"},
    timeout=30,
)

models = response.json()["data"]
print(f"{len(models)} models available:\n")

for m in sorted(models, key=lambda x: x["id"]):
    modalities = ",".join(m.get("input_modalities", ["text"]))
    ctx = m.get("context_window", "?")
    print(f"  {m['id']:<55}  ctx={ctx:>7}  in={modalities}")