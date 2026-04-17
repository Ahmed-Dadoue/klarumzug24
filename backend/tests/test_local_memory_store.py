import json
import os
import shutil
import stat
import unittest
import uuid

from app.ai.learning import local_memory


class LocalMemoryStoreTest(unittest.TestCase):
    def _make_tree_writable(self, root_path: str) -> None:
        for current_root, dirnames, filenames in os.walk(root_path, topdown=False):
            for filename in filenames:
                try:
                    os.chmod(os.path.join(current_root, filename), stat.S_IWRITE)
                except OSError:
                    pass
            for dirname in dirnames:
                try:
                    os.chmod(os.path.join(current_root, dirname), stat.S_IWRITE)
                except OSError:
                    pass
        try:
            os.chmod(root_path, stat.S_IWRITE)
        except OSError:
            pass

    def test_capture_and_review_flow(self) -> None:
        tmp_root = os.path.join(os.path.dirname(__file__), "_tmp")
        os.makedirs(tmp_root, exist_ok=True)
        temp_dir = os.path.join(tmp_root, f"local_memory_case_{uuid.uuid4().hex[:8]}")
        shutil.rmtree(temp_dir, ignore_errors=True)
        os.makedirs(temp_dir, exist_ok=True)
        previous_root = os.environ.get("DODE_LOCAL_MEMORY_ROOT")
        os.environ["DODE_LOCAL_MEMORY_ROOT"] = temp_dir
        try:
            capture = local_memory.capture_conversation_memory(
                {
                    "conversation_id": "conv_local_memory_01",
                    "conversation_type": "test_script",
                    "source_label": "pytest_harness",
                    "test_run_id": "run_local_memory",
                    "incoming_message": "Wie teuer ist eine Sofa-Entsorgung?",
                    "final_response": "Die Entsorgung startet je nach Umfang ab einer Schaetzung.",
                    "source_used": "tool",
                    "helper_path": "openai_primary_entsorgung_price",
                    "fallback_used": False,
                    "context_problems": [],
                    "repetition_signals": [],
                    "memory_review_required": True,
                    "candidate_knowledge": [
                        {
                            "memory_category": "service_knowledge",
                            "candidate_type": "service_pattern",
                            "question": "Wie teuer ist eine Sofa-Entsorgung?",
                            "answer": "Die Entsorgung startet je nach Umfang ab einer Schaetzung.",
                            "summary": "Entsorgungsanfrage fuer lokales Servicewissen.",
                            "service_type": "entsorgung",
                            "intent_type": "pricing_inquiry",
                            "confidence": 0.75,
                        }
                    ],
                }
            )
            self.assertTrue(capture["captured"])
            self.assertEqual(1, capture["candidates_created"])

            pending = [
                item
                for item in local_memory.list_review_candidates(status="pending", limit=10)
                if item.get("conversation_id") == "conv_local_memory_01"
            ]
            self.assertEqual(1, len(pending))
            candidate_id = pending[0]["candidate_id"]

            approved = local_memory.review_memory_candidate(
                candidate_id,
                decision="approve",
                reviewer="pytest",
                notes="sinnvoll fuer spaeteres Servicewissen",
            )
            self.assertIsNotNone(approved)
            self.assertEqual("approved", approved["review_status"])

            approved_items = [
                item
                for item in local_memory.list_review_candidates(status="approved", limit=10)
                if item.get("conversation_id") == "conv_local_memory_01"
            ]
            self.assertEqual(1, len(approved_items))

            stats = local_memory.get_memory_stats()
            self.assertEqual(1, stats["audit_records"])
            self.assertEqual(1, stats["approved_review"])
            self.assertEqual({"test_script": 1}, stats["by_conversation_type"])

            service_knowledge_file = os.path.join(
                temp_dir,
                "service_knowledge",
                "service_knowledge.jsonl",
            )
            with open(service_knowledge_file, "r", encoding="utf-8") as handle:
                lines = [json.loads(line) for line in handle.read().splitlines() if line.strip()]
            self.assertEqual(1, len(lines))
            self.assertEqual("service_pattern", lines[0]["candidate_type"])
        finally:
            if previous_root is None:
                os.environ.pop("DODE_LOCAL_MEMORY_ROOT", None)
            else:
                os.environ["DODE_LOCAL_MEMORY_ROOT"] = previous_root
            self._make_tree_writable(temp_dir)
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
