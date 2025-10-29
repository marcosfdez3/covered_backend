from google import genai

# The client gets the API key from the environment variable `GEMINI_API_KEY`.
client = genai.Client(api_key="AIzaSyDxheZwIwsRETWrYKl6_X4tJz-p5Fu58K0")

response = client.models.generate_content(
    model="gemini-2.5-flash", contents="España está gobernada por la derecha?"
)
print(response.text) 
