import unittest
import uuid
from unittest.mock import Mock, patch

from app.core.database import SessionLocal
from app.models import ChatSubmissionDB, LeadDB
from app.schemas import ChatMessageIn, ChatRequestIn
from app.services import chat_service
from app.services.lead_service import _mark_chat_conversation_submitted


class ChatBookingIntegrationTest(unittest.TestCase):
    def _payload(self, conversation_id: str, messages: list[ChatMessageIn]) -> ChatRequestIn:
        return ChatRequestIn(
            messages=messages,
            page="/kontakt.html",
            lang="de",
            conversation_id=conversation_id,
        )

    def _complete_messages(self, with_consent: bool) -> list[ChatMessageIn]:
        messages = [
            ChatMessageIn(role="user", content="mein name ist siba dadoue"),
            ChatMessageIn(role="user", content="ich moechte schrank aufbauen in kiel am exer"),
            ChatMessageIn(role="user", content="am 01.04.2026 um 06:00 uhr"),
            ChatMessageIn(role="user", content="emb19831@hotmail.com"),
            ChatMessageIn(role="user", content="01636157234"),
        ]
        if with_consent:
            messages.append(ChatMessageIn(role="user", content="Ja, ich stimme zu und senden"))
        return messages

    def _run_chat(
        self,
        payload: ChatRequestIn,
        *,
        generate_reply,
        create_lead,
    ):
        with patch.object(chat_service, "_save_learning_conversation", None), patch.object(
            chat_service,
            "_capture_local_memory",
            None,
        ):
            return chat_service.dode_chat(
                payload,
                generate_reply=generate_reply,
                create_lead=create_lead,
                serialize_lead=Mock(return_value={}),
                logger=Mock(),
            )

    def test_normal_flow_complete_data_without_consent(self) -> None:
        payload = self._payload("conv_ask_consent", self._complete_messages(with_consent=False))
        create_mock = Mock()

        with patch.object(chat_service, "_is_chat_conversation_submitted", return_value=False):
            response = self._run_chat(
                payload,
                generate_reply=Mock(return_value="AI reply"),
                create_lead=create_mock,
            )

        self.assertFalse(response["data"]["lead_submitted"])
        self.assertIn("Ja, ich stimme zu und senden", response["data"]["reply"])
        create_mock.assert_not_called()

    def test_duplicate_consent_blocked_when_conversation_already_submitted(self) -> None:
        payload = self._payload("conv_blocked", self._complete_messages(with_consent=True))
        create_mock = Mock()

        with patch.object(chat_service, "_is_chat_conversation_submitted", return_value=True), patch.object(
            chat_service,
            "_log_chat_submit_event",
        ) as log_submit_event_mock:
            response = self._run_chat(
                payload,
                generate_reply=Mock(return_value="AI reply"),
                create_lead=create_mock,
            )

        self.assertFalse(response["data"]["lead_submitted"])
        self.assertIn("Ihre Anfrage wurde bereits uebermittelt", response["data"]["reply"])
        create_mock.assert_not_called()
        log_submit_event_mock.assert_called_once()

    def test_incomplete_data_does_not_submit(self) -> None:
        payload = self._payload(
            "conv_incomplete",
            [
                ChatMessageIn(role="user", content="mein name ist ali"),
                ChatMessageIn(role="user", content="ich brauche montage"),
            ],
        )
        create_mock = Mock()

        with patch.object(chat_service, "_is_chat_conversation_submitted", return_value=False):
            response = self._run_chat(
                payload,
                generate_reply=Mock(return_value="AI reply"),
                create_lead=create_mock,
            )

        self.assertFalse(response["data"]["lead_submitted"])
        self.assertEqual("AI reply", response["data"]["reply"])
        create_mock.assert_not_called()

    def test_consent_without_data_does_not_submit(self) -> None:
        payload = self._payload(
            "conv_consent_only",
            [ChatMessageIn(role="user", content="Ja, ich stimme zu und senden")],
        )
        create_mock = Mock()

        with patch.object(chat_service, "_is_chat_conversation_submitted", return_value=False):
            response = self._run_chat(
                payload,
                generate_reply=Mock(return_value="AI reply"),
                create_lead=create_mock,
            )

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

        with patch.object(chat_service, "_is_chat_conversation_submitted", return_value=False), patch.object(
            chat_service,
            "_mark_chat_conversation_submitted",
            side_effect=mark_ok,
        ) as mark_mock:
            response_success = self._run_chat(
                payload_success,
                generate_reply=Mock(return_value="AI reply"),
                create_lead=Mock(side_effect=create_ok),
            )

        self.assertTrue(response_success["data"]["lead_submitted"])
        self.assertEqual(["create", "mark"], call_order)
        mark_mock.assert_called_once()

        payload_fail = self._payload("conv_fail", self._complete_messages(with_consent=True))
        with patch.object(chat_service, "_is_chat_conversation_submitted", return_value=False), patch.object(
            chat_service,
            "_mark_chat_conversation_submitted",
        ) as mark_mock_fail:
            response_fail = self._run_chat(
                payload_fail,
                generate_reply=Mock(return_value="AI reply"),
                create_lead=Mock(side_effect=RuntimeError("db error")),
            )

        self.assertFalse(response_fail["data"]["lead_submitted"])
        mark_mock_fail.assert_not_called()

    def test_mark_chat_conversation_submitted_blocks_duplicate_conversation_id(self) -> None:
        conversation_id = f"conv_mark_dup_{uuid.uuid4().hex[:12]}"
        db = SessionLocal()
        lead = LeadDB(
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
            first = _mark_chat_conversation_submitted(conversation_id, lead_id)
            second = _mark_chat_conversation_submitted(conversation_id, lead_id)
            self.assertTrue(first)
            self.assertFalse(second)
        finally:
            cleanup = SessionLocal()
            try:
                (
                    cleanup.query(ChatSubmissionDB)
                    .filter(ChatSubmissionDB.conversation_id == conversation_id)
                    .delete()
                )
                cleanup.query(LeadDB).filter(LeadDB.id == lead_id).delete()
                cleanup.commit()
            finally:
                cleanup.close()


if __name__ == "__main__":
    unittest.main()
