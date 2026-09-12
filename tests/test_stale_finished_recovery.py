import os
import sys
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dpdispatcher import Task
from dpdispatcher.utils.job_status import JobStatus


class TestStaleFinishedRecovery(unittest.TestCase):
    def test_missing_backward_file_reopens_task_and_quarantines_tag(self) -> None:
        task = Task("true", "task", backward_files=["result"])
        task.task_state = JobStatus.finished
        context = MagicMock()
        context.remote_root = "/remote/submission"
        context.check_file_exists.side_effect = lambda path: path.endswith(
            "_task_tag_finished"
        )
        context.sftp = MagicMock()

        task.reconcile_finished_state(context)

        self.assertEqual(task.task_state, JobStatus.unsubmitted)
        context.sftp.rename.assert_called_once()
        self.assertTrue(
            context.sftp.rename.call_args.args[1].endswith(".stale-recovery")
        )

    def test_complete_backward_file_keeps_finished_task(self) -> None:
        task = Task("true", "task", backward_files=["result"])
        task.task_state = JobStatus.finished
        context = MagicMock()
        context.check_file_exists.return_value = True
        context.sftp = MagicMock()

        task.reconcile_finished_state(context)

        self.assertEqual(task.task_state, JobStatus.finished)
        context.sftp.rename.assert_not_called()


if __name__ == "__main__":
    unittest.main()
