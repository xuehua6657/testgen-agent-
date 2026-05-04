"""LLM-powered test generation for TestGen-Agent."""

import time

from openai import OpenAI

from testgen.config import LLMConfig
from testgen.utils import extract_code_blocks, get_logger


class TestGenerator:
    """Generates test cases using LLM."""

    def __init__(self, config: LLMConfig):
        """Initialize the test generator.

        Args:
            config: LLM configuration.
        """
        self.config = config
        self.logger = get_logger()
        self.client = OpenAI(
            api_key=config.api_key.get_secret_value(),
            base_url=config.base_url,
            timeout=config.timeout,
        )
        self.model = config.model
        self.temperature = config.temperature
        self.max_tokens = config.max_tokens

    def generate_tests(self, prompt: str, system_prompt: str) -> str:
        """Send prompt to LLM and return generated test code.

        Args:
            prompt: User prompt with code change details.
            system_prompt: System prompt with rules and instructions.

        Returns:
            Generated test code string.

        Raises:
            RuntimeError: If LLM call fails after retries.
        """
        self.logger.info(f"Calling LLM ({self.model}) for test generation...")

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )

        content = response.choices[0].message.content or ""
        self.logger.info(f"LLM response received ({len(content)} chars)")

        return content

    def generate_with_retry(
        self, prompt: str, system_prompt: str, max_retries: int = 3
    ) -> str:
        """Generate tests with automatic retry on failure.

        Uses exponential backoff between retries. On each failure,
        appends error context to prompt for retry.

        Args:
            prompt: User prompt.
            system_prompt: System prompt.
            max_retries: Maximum number of retry attempts.

        Returns:
            Generated test code string.

        Raises:
            RuntimeError: If all retries are exhausted.
        """
        last_error = None

        for attempt in range(1, max_retries + 1):
            try:
                result = self.generate_tests(prompt, system_prompt)
                if result.strip():
                    return result
                self.logger.warning(f"Attempt {attempt}: Empty response from LLM")
            except Exception as e:
                last_error = e
                self.logger.warning(f"Attempt {attempt} failed: {e}")

            if attempt < max_retries:
                wait_time = 2 ** attempt
                self.logger.info(f"Retrying in {wait_time}s...")
                time.sleep(wait_time)

                # Append error context to prompt for retry
                prompt += f"\n\n[Previous attempt failed: {last_error}. Please retry.]"

        raise RuntimeError(
            f"Test generation failed after {max_retries} attempts. Last error: {last_error}"
        )

    def extract_code(self, response: str, language: str = "python") -> list[str]:
        """Extract code blocks from LLM response.

        Handles both markdown-fenced and plain code responses.

        Args:
            response: Raw LLM response text.
            language: Expected programming language.

        Returns:
            List of extracted code strings.
        """
        blocks = extract_code_blocks(response, language)
        if blocks:
            self.logger.debug(f"Extracted {len(blocks)} code block(s)")
            return blocks

        # If no blocks found, return the whole response
        self.logger.warning("No code blocks found in response, returning full text")
        return [response.strip()] if response.strip() else []
