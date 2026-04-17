import unittest
from unittest.mock import Mock, patch

from app.schemas import ChatMessageIn, ChatRequestIn
from app.services import chat_service


class _DummySession:
    def close(self) -> None:
        return None


class ChatServiceLearningMetadataTest(unittest.TestCase):
    def test_learning_snapshot_stores_intent_and_service_type(self) -> None:
        payload = ChatRequestIn(
            messages=[ChatMessageIn(role="user", content="Was kostet die Entsorgung von 3 Sofas?")],
            page="/kontakt.html",
            lang="de",
            conversation_id="conv_learning_meta",
        )
        save_mock = Mock()

        with patch.object(chat_service, "_save_learning_conversation", save_mock), patch.object(
            chat_service,
            "_capture_local_memory",
            Mock(return_value={"captured": False, "review_required": False, "candidates_created": 0}),
        ), patch.object(
            chat_service,
            "SessionLocal",
            return_value=_DummySession(),
        ), patch.object(chat_service, "_is_chat_conversation_submitted", return_value=False):
            chat_service.dode_chat(
                payload,
                generate_reply=Mock(return_value="AI reply"),
                create_lead=Mock(),
                serialize_lead=Mock(return_value={}),
                logger=Mock(),
            )

        self.assertTrue(save_mock.called)
        _, kwargs = save_mock.call_args
        self.assertEqual("entsorgung", kwargs["service_type"])
        self.assertEqual("pricing_inquiry", kwargs["intent_type"])
        self.assertEqual("real_user", kwargs["conversation_type"])
        self.assertEqual("chat_completed", kwargs["outcome"])


if __name__ == "__main__":
    unittest.main()
