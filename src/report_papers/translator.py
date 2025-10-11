"""Text translation service using Amazon Translate."""

import os

import boto3

from .logger import get_logger

logger = get_logger(__name__)


class Translator:
    """Amazon Translate-based text translation service."""

    def __init__(self, region: str, target_language: str):
        """
        Initialize translator.

        Args:
            region: AWS region for Amazon Translate
            target_language: Target language code (ISO 639-1, e.g., 'ja', 'en', 'es')
        """
        self.target_language = target_language
        translate_endpoint = os.getenv("TRANSLATE_ENDPOINT")
        self.translate_client = boto3.client(
            "translate", region_name=region, endpoint_url=translate_endpoint
        )

    def translate_text(self, text: str) -> str:
        """
        Translate text to the target language using Amazon Translate.

        Args:
            text: Text to translate

        Returns:
            Translated text in target language, or original text if translation fails or target is 'en'
        """
        if not text or not text.strip():
            return text

        # Skip translation if target language is English
        if self.target_language == "en":
            return text

        try:
            response = self.translate_client.translate_text(
                Text=text,
                SourceLanguageCode="en",
                TargetLanguageCode=self.target_language,
                Settings={"Formality": "FORMAL"},
            )
            translated_text = response["TranslatedText"]
            logger.info(
                f"Successfully translated text to {self.target_language}: "
                f"{len(text)} chars -> {len(translated_text)} chars"
            )
            return str(translated_text)

        except Exception as e:
            logger.warning(f"Failed to translate text to {self.target_language}: {e}")
            return text  # Return original text if translation fails
