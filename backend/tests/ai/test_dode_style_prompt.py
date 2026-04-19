import unittest

from app.ai.prompts import build_dode_system_prompt
from app.ai.prompts_v2 import build_dode_system_prompt_v2


class DodeStylePromptTest(unittest.TestCase):
    def test_primary_prompt_limits_repeated_thanks(self) -> None:
        prompt = build_dode_system_prompt("/kontakt.html", lang="de")

        self.assertIn("Bedanke dich nicht bei jeder einzelnen Angabe", prompt)
        self.assertIn("serioeser, menschlicher Disponent", prompt)
        self.assertIn("direkt zur naechsten sinnvollen Frage", prompt)

    def test_v2_prompt_limits_repeated_thanks(self) -> None:
        prompt = build_dode_system_prompt_v2("/kontakt.html", service_type="moebelmontage", lang="de")

        self.assertIn("Nicht bei jeder Kundenaussage bedanken", prompt)
        self.assertIn("Vielen Dank fuer die Angabe", prompt)
        self.assertIn("serioeser, respektvoller Disponent", prompt)


if __name__ == "__main__":
    unittest.main()
