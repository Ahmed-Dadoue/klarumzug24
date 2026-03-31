import unittest
import uuid
from unittest.mock import patch

import main


class ChatBookingIntegrationTest(unittest.TestCase):
    def _payload(self, conversation_id: str, messages: list[main.ChatMessageIn]) -> main.ChatRequestIn:
        return main.ChatRequestIn(
            messages=messages,
            page="/kontakt.html",
            lang="de",
            conversation_id=conversation_id,
        )

    def _complete_messages(self, with_consent: bool) -> list[main.ChatMessageIn]:
        messages = [
            main.ChatMessageIn(role="user", content="mein name ist siba dadoue"),
            main.ChatMessageIn(role="user", content="ich moechte schrank aufbauen in kiel am exer"),
            main.ChatMessageIn(role="user", content="am 01.04.2026 um 06:00 uhr"),
            main.ChatMessageIn(role="user", content="emb19831@hotmail.com"),
            main.ChatMessageIn(role="user", content="01636157234"),
        ]
        if with_consent:
            messages.append(main.ChatMessageIn(role="user", content="Ja, ich stimme zu und senden"))
        return messages

    def test_normal_flow_complete_data_without_consent(self) -> None:
        payload = self._payload("conv_ask_consent", self._complete_messages(with_consent=False))

        with patch.object(main, "generate_dode_reply", return_value="AI reply"), \
            patch.object(main, "_is_chat_conversation_submitted", return_value=False), \
            patch.object(main, "_create_lead") as create_mock:
            response = main.dode_chat(payload)

        self.assertFalse(response["data"]["lead_submitted"])
        self.assertIn("Ja, ich stimme zu und senden", response["data"]["reply"])
        create_mock.assert_not_called()

    def test_duplicate_consent_blocked_when_conversation_already_submitted(self) -> None:
        payload = self._payload("conv_blocked", self._complete_messages(with_consent=True))

        with patch.object(main, "generate_dode_reply", return_value="AI reply"), \
            patch.object(main, "_is_chat_conversation_submitted", return_value=True), \
            patch.object(main, "_create_lead") as create_mock, \
            patch.object(main, "_log_chat_submit_event") as log_submit_event_mock:
            response = main.dode_chat(payload)

        self.assertFalse(response["data"]["lead_submitted"])
        self.assertIn("Ihre Anfrage wurde bereits uebermittelt", response["data"]["reply"])
        create_mock.assert_not_called()
        log_submit_event_mock.assert_called_once()

    def test_incomplete_data_does_not_submit(self) -> None:
        payload = self._payload(
            "conv_incomplete",
            [
                main.ChatMessageIn(role="user", content="mein name ist ali"),
                main.ChatMessageIn(role="user", content="ich brauche montage"),
            ],
        )

        with patch.object(main, "generate_dode_reply", return_value="AI reply"), \
            patch.object(main, "_is_chat_conversation_submitted", return_value=False), \
            patch.object(main, "_create_lead") as create_mock:
            response = main.dode_chat(payload)

        self.assertFalse(response["data"]["lead_submitted"])
        self.assertEqual("AI reply", response["data"]["reply"])
        create_mock.assert_not_called()

    def test_consent_without_data_does_not_submit(self) -> None:
        payload = self._payload(
            "conv_consent_only",
            [main.ChatMessageIn(role="user", content="Ja, ich stimme zu und senden")],
        )

        with patch.object(main, "generate_dode_reply", return_value="AI reply"), \
            patch.object(main, "_is_chat_conversation_submitted", return_value=False), \
            patch.object(main, "_create_lead") as create_mock:
            response = main.dode_chat(payload)

        self.assertFalse(response["data"]["lead_submitted"])
        self.assertEqual("AI reply", response["data"]["reply"])
        create_mock.assert_not_called()

    def test_mark_submitted_only_after_successful_create_lead_and_not_on_error(self) -> None:
        payload_success = self._payload("conv_success", self._complete_messages(with_consent=True))
        call_order: list[str] = []

        def create_ok(*args, **kwargs):
            call_order.append("create")
            return {"data": {"lead_id": 321}}

        def mark_ok(*args, **kwargs):
            call_order.append("mark")
            return True

        with patch.object(main, "generate_dode_reply", return_value="AI reply"), \
            patch.object(main, "_is_chat_conversation_submitted", return_value=False), \
            patch.object(main, "_create_lead", side_effect=create_ok), \
            patch.object(main, "_mark_chat_conversation_submitted", side_effect=mark_ok) as mark_mock:
            response_success = main.dode_chat(payload_success)

        self.assertTrue(response_success["data"]["lead_submitted"])
        self.assertEqual(["create", "mark"], call_order)
        mark_mock.assert_called_once()

        payload_fail = self._payload("conv_fail", self._complete_messages(with_consent=True))
        with patch.object(main, "generate_dode_reply", return_value="AI reply"), \
            patch.object(main, "_is_chat_conversation_submitted", return_value=False), \
            patch.object(main, "_create_lead", side_effect=RuntimeError("db error")), \
            patch.object(main, "_mark_chat_conversation_submitted") as mark_mock_fail:
            response_fail = main.dode_chat(payload_fail)

        self.assertFalse(response_fail["data"]["lead_submitted"])
        mark_mock_fail.assert_not_called()

    def test_mark_chat_conversation_submitted_blocks_duplicate_conversation_id(self) -> None:
        conversation_id = f"conv_mark_dup_{uuid.uuid4().hex[:12]}"
        db = main.SessionLocal()
        lead = main.LeadDB(
            name="Submit Guard Test",
            phone=f"0151{uuid.uuid4().int % 100000000:08d}",
            email=f"submit-guard-{uuid.uuid4().hex[:8]}@example.com",
            accepted_agb=True,
            accepted_privacy=True,
            status="new",
        )
        db.add(lead)
        db.commit()
        db.refresh(lead)
        lead_id = int(lead.id)
        db.close()

        try:
            first = main._mark_chat_conversation_submitted(conversation_id, lead_id)
            second = main._mark_chat_conversation_submitted(conversation_id, lead_id)
            self.assertTrue(first)
            self.assertFalse(second)
        finally:
            cleanup = main.SessionLocal()
            try:
                (
                    cleanup.query(main.ChatSubmissionDB)
                    .filter(main.ChatSubmissionDB.conversation_id == conversation_id)
                    .delete()
                )
                cleanup.query(main.LeadDB).filter(main.LeadDB.id == lead_id).delete()
                cleanup.commit()
            finally:
                cleanup.close()


if __name__ == "__main__":
    unittest.main()
