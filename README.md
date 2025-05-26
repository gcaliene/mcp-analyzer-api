# coretext-interview-project

## Running with Docker

1. **Copy and configure environment variables:**
   
   Copy the example env file and fill in your secrets:
   ```sh
   cp .env.example .env
   # Edit .env and set ANTHROPIC_API_KEY and GITHUB_TOKEN
   ```

2. **Build the Docker image:**
   ```sh
   docker build -t coretext-interview-project .
   ```

3. **Run the container:**
   ```sh
   docker run --env-file .env -p 8001:8001 coretext-interview-project
   ```
   - The FastAPI client will be available at [http://localhost:8001](http://localhost:8001)
   - The GitHub analysis server runs internally on port 8000

---

- Ensure your `.env` file is present in the project root before running the container.
- The container exposes port 8001 for the FastAPI client API.
