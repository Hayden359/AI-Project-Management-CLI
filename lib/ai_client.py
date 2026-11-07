import ollama


class OllamaChatClient:
    """reusable client for interacting with a local chat model service."""

    def __init__(self, model_name="llama3.2"):
        self.model_name = model_name
        self.history = []

    def send(self, prompt):
        if prompt is None:
            raise ValueError("Prompt cannot be empty")
        if not isinstance(prompt, str):
            raise ValueError("Prompt must be a string")

        prompt = prompt.strip()

        if not prompt:
            raise ValueError("Prompt cannot be empty")

        user_message = {"role": "user", "content": prompt}
        self.history.append(user_message)

        try:
            response = ollama.chat(model=self.model_name, messages=self.history)
        except Exception as exc:
            self.history.pop()
            raise RuntimeError(f"AI service request failed: {exc}") from exc

        if isinstance(response, dict):
            message = response.get("message")
            content = message.get("content") if isinstance(message, dict) else None
        else:
            message = getattr(response, "message", None)
            content = getattr(message, "content", None)

        if not isinstance(content, str) or not content.strip():
            self.history.pop()
            raise RuntimeError("AI service request failed: invalid assistant response")

        content = content.strip()
        self.history.append({"role": "assistant", "content": content})
        return content

    def reset(self):
        """Clear the conversation history."""
        self.history.clear()

    def message_count(self):
        """Return the number of stored messages."""
        return len(self.history)

    def get_transcript(self):
        """Return a safe copy of the conversation history."""
        return [message.copy() for message in self.history]