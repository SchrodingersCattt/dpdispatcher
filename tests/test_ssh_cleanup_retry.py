import os
import sys
import unittest
from unittest.mock import MagicMock, call, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dpdispatcher.contexts.ssh_context import SSHContext


class TestSSHCleanupRetry(unittest.TestCase):
    """Verify bounded retries for transient SSH cleanup failures."""

    def setUp(self) -> None:
        self.context = SSHContext.__new__(SSHContext)
        self.context.clean_asynchronously = False
        self.context.block_checkcall = MagicMock()

    @patch("dpdispatcher.contexts.ssh_context.time.sleep")
    def test_rmtree_retries_transient_failure(
        self, sleep: MagicMock
    ) -> None:
        """Retry a transient directory metadata race."""
        self.context.block_checkcall.side_effect = [
            RuntimeError("Directory not empty"),
            None,
        ]

        self.context._rmtree("/remote/root")

        self.assertEqual(
            self.context.block_checkcall.call_args_list,
            [
                call("rm -rf /remote/root", asynchronously=False),
                call("rm -rf /remote/root", asynchronously=False),
            ],
        )
        sleep.assert_called_once_with(1)

    @patch("dpdispatcher.contexts.ssh_context.time.sleep")
    def test_rmtree_propagates_non_transient_failure(
        self, sleep: MagicMock
    ) -> None:
        """Propagate unrelated cleanup failures without retrying."""
        self.context.block_checkcall.side_effect = RuntimeError("permission denied")

        with self.assertRaisesRegex(RuntimeError, "permission denied"):
            self.context._rmtree("/remote/root")

        self.context.block_checkcall.assert_called_once_with(
            "rm -rf /remote/root", asynchronously=False
        )
        sleep.assert_not_called()

    @patch("dpdispatcher.contexts.ssh_context.time.sleep")
    def test_rmtree_retries_nfs_busy_failure(
        self, sleep: MagicMock
    ) -> None:
        """Retry a busy NFS temporary file left by an open handle."""
        self.context.block_checkcall.side_effect = [
            RuntimeError(".nfs0001: Device or resource busy"),
            None,
        ]

        self.context._rmtree("/remote/root")

        self.assertEqual(self.context.block_checkcall.call_count, 2)
        sleep.assert_called_once_with(1)

    @patch("dpdispatcher.contexts.ssh_context.time.sleep")
    def test_rmtree_propagates_non_nfs_busy_failure(
        self, sleep: MagicMock
    ) -> None:
        """Do not retry a busy error unrelated to an NFS temporary file."""
        self.context.block_checkcall.side_effect = RuntimeError(
            "/mnt/active: Device or resource busy"
        )

        with self.assertRaisesRegex(RuntimeError, "Device or resource busy"):
            self.context._rmtree("/remote/root")

        self.context.block_checkcall.assert_called_once_with(
            "rm -rf /remote/root", asynchronously=False
        )
        sleep.assert_not_called()

    @patch("dpdispatcher.contexts.ssh_context.time.sleep")
    def test_rmtree_raises_after_retry_exhaustion(
        self, sleep: MagicMock
    ) -> None:
        """Raise the original transient error after bounded retries."""
        self.context.block_checkcall.side_effect = RuntimeError("Directory not empty")

        with self.assertRaisesRegex(RuntimeError, "Directory not empty"):
            self.context._rmtree("/remote/root")

        self.assertEqual(self.context.block_checkcall.call_count, 3)
        self.assertEqual(sleep.call_args_list, [call(1), call(2)])

    def test_async_cleanup_does_not_retry(self) -> None:
        """Keep asynchronous cleanup as a single nonblocking call."""
        self.context.clean_asynchronously = True

        self.context._rmtree("/remote/root")

        self.context.block_checkcall.assert_called_once_with(
            "rm -rf /remote/root", asynchronously=True
        )


if __name__ == "__main__":
    unittest.main()
