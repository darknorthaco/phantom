import unittest

from phantom_next import CeremonyPhase, CeremonyStateMachine


class CeremonyStateMachineTests(unittest.TestCase):
    def test_happy_path_reaches_operational(self) -> None:
        machine = CeremonyStateMachine(correlation_id="test-correlation")

        machine.transition(CeremonyPhase.PLACEMENT, summary="Act A complete")
        machine.transition(CeremonyPhase.MATERIALIZE, summary="Act B complete")
        machine.transition(CeremonyPhase.DISCOVER, summary="Act C complete")
        machine.transition(CeremonyPhase.CONFIGURE, summary="Act D complete")
        machine.transition(CeremonyPhase.ATTEST, summary="Act E complete")
        machine.transition(CeremonyPhase.REGISTER, summary="Act F complete")
        machine.transition(CeremonyPhase.OPERATIONAL, summary="Operational")

        self.assertTrue(machine.operational)
        self.assertEqual(machine.last_completed_act, "F")
        self.assertEqual(len(machine.history), 7)

    def test_invalid_transition_rejected(self) -> None:
        machine = CeremonyStateMachine(correlation_id="test-correlation")
        with self.assertRaises(ValueError):
            machine.transition(CeremonyPhase.CONFIGURE, summary="invalid jump")


if __name__ == "__main__":
    unittest.main()
