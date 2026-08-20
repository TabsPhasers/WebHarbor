from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SITE_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = SITE_ROOT.parents[1]
sys.path.insert(0, str(SITE_ROOT / "verify"))
sys.path.insert(0, str(SITE_ROOT))

from rate_quote import QuoteRequest, issue_quote_token  # noqa: E402
from verify_lib import TASK_SPECS, answer_contains, semantic_answer_matches  # noqa: E402


class FedExTaskContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tasks = [
            json.loads(line)
            for line in (SITE_ROOT / "tasks.jsonl").read_text().splitlines()
            if line.strip()
        ]

    def run_verifier(self, index: int, trajectory: dict) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as run_dir:
            (Path(run_dir) / "trajectory.json").write_text(json.dumps(trajectory))
            return subprocess.run(
                [
                    sys.executable,
                    str(SITE_ROOT / "verify" / f"verify_{index}.py"),
                    "--run_dir",
                    run_dir,
                    "--no_llm",
                    "true",
                ],
                cwd=REPOSITORY_ROOT,
                capture_output=True,
                text=True,
            )

    def test_all_eighteen_tasks_have_one_verifier_and_one_rubric(self) -> None:
        self.assertEqual(len(self.tasks), 18)
        self.assertEqual(
            [task["id"] for task in self.tasks],
            [f"FedEx--{index}" for index in range(18)],
        )

        verifier_paths = []
        for task in self.tasks:
            self.assertEqual(
                set(task),
                {
                    "web_name",
                    "id",
                    "ques",
                    "web",
                    "upstream_url",
                    "verifier_path",
                    "judge_rubric",
                },
            )
            verifier_path = task["verifier_path"]
            self.assertTrue(verifier_path.startswith("sites/fedex/verify/verify_"))
            self.assertTrue((REPOSITORY_ROOT / verifier_path).is_file())
            self.assertTrue(task["judge_rubric"].startswith("FACT CHECKPOINTS:"))
            self.assertIn("FAIL if:", task["judge_rubric"])
            verifier_paths.append(verifier_path)

        self.assertEqual(len(set(verifier_paths)), len(self.tasks))

    def test_every_login_task_supplies_the_demo_password(self) -> None:
        login_tasks = [task for task in self.tasks if "Sign in as" in task["ques"]]
        self.assertGreater(len(login_tasks), 0)
        for task in login_tasks:
            self.assertIn("TestPass123!", task["ques"], task["id"])

    def test_repaired_tasks_require_unambiguous_detail_or_comparison_facts(self) -> None:
        questions = {task["id"]: task["ques"] for task in self.tasks}
        self.assertIn("latest exception timeline entry", questions["FedEx--0"])
        self.assertIn("signature", questions["FedEx--1"].lower())
        self.assertIn("search for tracking", questions["FedEx--2"].lower())
        self.assertIn("related-topic chips", questions["FedEx--2"])
        self.assertIn("price difference", questions["FedEx--4"])
        self.assertIn("delivered to Dallas, TX", questions["FedEx--5"])
        self.assertIn("every shipment", questions["FedEx--8"])
        self.assertIn("article body", questions["FedEx--11"])
        self.assertIn("final timeline", questions["FedEx--16"])

    def test_rubrics_do_not_contain_frozen_answers(self) -> None:
        forbidden_answers = {
            "FedEx--0": ["Los Angeles", "weather conditions"],
            "FedEx--1": ["FDX260000001", "signature required"],
            "FedEx--2": ["demo workflow", "tracking help"],
            "FedEx--3": ["$37.40"],
            "FedEx--4": ["$43.80"],
            "FedEx--5": ["INV-260001"],
            "FedEx--6": ["CLM-2623"],
            "FedEx--7": ["PU-2621"],
            "FedEx--8": ["SH-260050", "SH-260055", "SH-260060"],
            "FedEx--9": ["4:45 PM"],
            "FedEx--10": ["5:45 PM"],
            "FedEx--11": ["tracking, billing, and pickup"],
            "FedEx--12": ["FDX260000061"],
            "FedEx--13": ["PU-2609"],
            "FedEx--14": ["7:00 AM - 9:00 PM"],
            "FedEx--15": ["CLM-2653"],
            "FedEx--16": ["Los Angeles"],
            "FedEx--17": ["$191.40"],
        }
        for task in self.tasks:
            rubric = task["judge_rubric"].casefold()
            for answer in forbidden_answers[task["id"]]:
                self.assertNotIn(answer.casefold(), rubric, task["id"])

    def test_frozen_answers_cover_every_deterministic_fact_group(self) -> None:
        frozen_answers = {
            0: "Los Angeles, CA — weather conditions paused the handoff.",
            1: "FDX260000001 is delivered; yes, signature is required.",
            2: "The chips are demo workflow and tracking help.",
            3: "FedEx Ground Home Delivery — $37.40.",
            4: "The fastest is FedEx Priority Overnight; the cheapest is FedEx Ground Home Delivery; the difference is $43.80.",
            5: "INV-260001",
            6: "CLM-2623; FDX260000023",
            7: "PU-2621, 9:00 AM - 11:00 AM",
            8: "SH-260050 Charlotte; SH-260055 Los Angeles; SH-260060 Seattle",
            9: "Freight cutoff 4:45 PM",
            10: "International docs accepted until 5:45 PM",
            11: "tracking, billing, and pickup",
            12: "FDX260000061",
            13: "PU-2609",
            14: "7:00 AM - 9:00 PM",
            15: "CLM-2653; FDX260000053",
            16: "Delivered in Los Angeles, CA",
            17: "FedEx Freight Economy — $191.40",
        }
        for index, answer in frozen_answers.items():
            for alternatives in TASK_SPECS[index].answer_groups:
                self.assertTrue(
                    any(answer_contains(answer, alternative) for alternative in alternatives),
                    f"FedEx--{index}: {alternatives!r} not matched by {answer!r}",
                )
            self.assertTrue(semantic_answer_matches(index, answer), f"FedEx--{index}: semantic rejection")

    def test_short_tokens_and_prices_require_boundaries(self) -> None:
        self.assertFalse(answer_contains("The package is located nearby.", "ca"))
        self.assertFalse(answer_contains("The displayed price is $137.40.", "37.4"))
        self.assertTrue(answer_contains("The final state is CA.", "ca"))
        self.assertTrue(answer_contains("The displayed price is 37.4 dollars.", "37.4"))

    def test_reversed_negated_and_extra_claims_are_rejected(self) -> None:
        adversarial_answers = {
            1: "FDX260000001 is not delivered and signature is not required.",
            3: "FedEx Ground Home Delivery is not cheapest at $37.40.",
            4: "FedEx Ground Home Delivery is fastest and FedEx Priority Overnight is cheapest; difference $43.80.",
            5: "The answer is not INV-260001.",
            8: "SH-260050 Charlotte; SH-260055 Los Angeles; SH-260060 Seattle; SH-260046 Washington.",
            12: "The generated numbers are FDX260000061 and FDX260000999.",
            16: "It is not delivered and is still moving; final handoff Los Angeles, CA.",
            17: "FedEx Freight Economy is not most expensive at $191.40.",
        }
        for index, answer in adversarial_answers.items():
            self.assertFalse(semantic_answer_matches(index, answer), f"FedEx--{index}: {answer}")

    def test_quote_answer_without_submitting_requested_inputs_is_rejected(self) -> None:
        known_answers = {
            3: "FedEx Ground Home Delivery is cheapest at $37.40.",
            4: "The fastest is FedEx Priority Overnight; the cheapest is FedEx Ground Home Delivery; the difference is $43.80.",
            17: "FedEx Freight Economy is most expensive at $191.40.",
        }
        for index, answer in known_answers.items():
            trajectory = {
                "task_id": f"FedEx--{index}",
                "steps": [{"url": "http://localhost:40016/rate-estimate"}],
                "final_answer": answer,
            }
            completed = self.run_verifier(index, trajectory)
            self.assertEqual(1, completed.returncode, f"FedEx--{index}: {completed.stdout}")

    def test_replayed_signed_quote_without_a_successful_form_submit_is_rejected(self) -> None:
        token = issue_quote_token(QuoteRequest("CA", "TX", 8, "Box"))
        quote_url = f"http://localhost:40016/rate-estimate?quote={token}"
        trajectories = (
            {
                "task_id": "FedEx--3",
                "steps": [
                    {
                        "url": "http://localhost:40016/rate-estimate",
                        "action": "navigate",
                        "action_result": {"success": True, "url_after": quote_url},
                    }
                ],
                "final_answer": "FedEx Ground Home Delivery is cheapest at $37.40.",
            },
            {
                "task_id": "FedEx--3",
                "steps": [
                    {
                        "url": quote_url,
                        "action": "click",
                        "action_result": {"success": False, "url_after": quote_url},
                    }
                ],
                "final_answer": "FedEx Ground Home Delivery is cheapest at $37.40.",
            },
        )
        for trajectory in trajectories:
            completed = self.run_verifier(3, trajectory)
            self.assertEqual(1, completed.returncode, completed.stdout)

    def test_equivalent_hour_formats_are_accepted(self) -> None:
        cases = {
            7: (["/login", "/account"], "PU-2621, 9 a.m.–11 a.m."),
            14: (["/search", "/locations/seattle-downtown-wa"], "7 a.m.–9 p.m."),
        }
        for index, (paths, answer) in cases.items():
            trajectory = {
                "task_id": f"FedEx--{index}",
                "steps": [{"url": f"http://localhost:40016{path}"} for path in paths],
                "final_answer": answer,
            }
            completed = self.run_verifier(index, trajectory)
            self.assertEqual(0, completed.returncode, f"FedEx--{index}: {completed.stdout}")

    def test_quote_fields_filled_after_an_unrelated_click_are_not_treated_as_submitted(self) -> None:
        trajectory = {
            "task_id": "FedEx--3",
            "steps": [
                {"url": "http://localhost:40016/rate-estimate", "action": "select", "params": {"value": "CA"}},
                {"url": "http://localhost:40016/rate-estimate", "action": "click", "params": {"index": 1}},
                {"url": "http://localhost:40016/rate-estimate", "action": "select", "params": {"value": "TX"}},
                {"url": "http://localhost:40016/rate-estimate", "action": "input", "params": {"text": "8"}},
                {"url": "http://localhost:40016/rate-estimate", "action": "select", "params": {"value": "Box"}},
            ],
            "final_answer": "FedEx Ground Home Delivery is cheapest at $37.40.",
        }
        completed = self.run_verifier(3, trajectory)
        self.assertEqual(1, completed.returncode, completed.stdout)

    def test_values_typed_into_arbitrary_fields_do_not_count_as_a_quote_submission(self) -> None:
        cases = {
            3: (["CA", "TX", "8", "Box"], "FedEx Ground Home Delivery is cheapest at $37.40."),
            4: (["WA", "FL", "4", "Envelope"], "The fastest is FedEx Priority Overnight; the cheapest is FedEx Ground Home Delivery; the difference is $43.80."),
            17: (["TX", "FL", "12", "Freight pallet"], "FedEx Freight Economy is most expensive at $191.40."),
        }
        for index, (values, answer) in cases.items():
            steps = [
                {
                    "url": "http://localhost:40016/rate-estimate",
                    "action": "input",
                    "params": {"index": position, "text": value},
                }
                for position, value in enumerate(values, start=1)
            ]
            steps.append(
                {
                    "url": "http://localhost:40016/rate-estimate",
                    "action": "click",
                    "params": {"index": 5},
                }
            )
            trajectory = {
                "task_id": f"FedEx--{index}",
                "steps": steps,
                "final_answer": answer,
            }
            completed = self.run_verifier(index, trajectory)
            self.assertEqual(1, completed.returncode, f"FedEx--{index}: {completed.stdout}")


if __name__ == "__main__":
    unittest.main()
