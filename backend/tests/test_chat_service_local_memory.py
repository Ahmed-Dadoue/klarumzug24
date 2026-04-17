import unittest
from unittest.mock import Mock, patch

from app.schemas import ChatMessageIn, ChatRequestIn
from app.services import chat_service


class _DummySession:
    def close(self) -> None:
        return None


def _generate_reply_with_trace(**kwargs):
    trace = kwargs.get("trace")
    if isinstance(trace, dict):
        trace.update(
            {
                "source_used": "pricing",
                "helper_path": "openai_primary_move_price",
                "fallback_used": False,
                "faq_meta": {},
            }
        )
    return "Hier ist Ihre unverbindliche Schaetzung."


class ChatServiceLocalMemoryTest(unittest.TestCase):
    def test_test_script_metadata_and_memory_capture_are_forwarded(self) -> None:
        payload = ChatRequestIn(
            messages=[ChatMessageIn(role="user", content="Was kostet ein Umzug von Kiel nach Hamburg?")],
            page="/umzugsrechner.html",
            lang="de",
            conversation_id="harness_case_01",
            conversation_type="test_script",
            source_label="pytest_harness",
            test_run_id="run_local_01",
            memory_review_required=True,
        )
        save_mock = Mock()
        memory_mock = Mock(
            return_value={
                "captured": True,
                "review_required": True,
                "candidates_created": 2,
                "candidate_ids": ["mem_a", "mem_b"],
            }
        )

        with patch.object(chat_service, "_save_learning_conversation", save_mock), patch.object(
            chat_service,
            "_capture_local_memory",
            memory_mock,
        ), patch.object(
            chat_service,
            "SessionLocal",
            return_value=_DummySession(),
        ), patch.object(chat_service, "_is_chat_conversation_submitted", return_value=False):
            response = chat_service.dode_chat(
                payload,
                generate_reply=_generate_reply_with_trace,
                create_lead=Mock(),
                serialize_lead=Mock(return_value={}),
                logger=Mock(),
            )

        self.assertTrue(memory_mock.called)
        memory_record = memory_mock.call_args.args[0]
        self.assertEqual("test_script", memory_record["conversation_type"])
        self.assertEqual("pytest_harness", memory_record["source_label"])
        self.assertEqual("run_local_01", memory_record["test_run_id"])
        self.assertEqual("pricing", memory_record["source_used"])
        self.assertEqual("openai_primary_move_price", memory_record["helper_path"])

        self.assertTrue(save_mock.called)
        _, kwargs = save_mock.call_args
        self.assertEqual("test_script", kwargs["conversation_type"])
        self.assertEqual("pytest_harness", kwargs["source_label"])
        self.assertEqual("run_local_01", kwargs["test_run_id"])
        self.assertEqual("pricing", kwargs["source_used"])
        self.assertEqual("openai_primary_move_price", kwargs["helper_path"])
        self.assertFalse(kwargs["fallback_used"])
        self.assertIn("memory_capture", kwargs["telemetry"])

        supervisor = response["data"]["supervisor"]
        self.assertEqual("test_script", supervisor["conversation_type"])
        self.assertEqual("pricing", supervisor["source_used"])
        self.assertEqual(2, supervisor["memory_candidates_created"])


if __name__ == "__main__":
    unittest.main()
