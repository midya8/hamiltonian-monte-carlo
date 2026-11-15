"""Finite endpoint energies need not have a finite binary64 difference."""
import json
import math
import random
import unittest
from hamiltonlab.core import accept, leapfrog, sample


def cubic_target(scale):
    def target(q):
        x = q[0]
        return scale*(1.5*x-.5*x*x*x), [1.5*scale*(1-x*x), 0.]
    return target


def smooth_target(q):
    t = math.tanh(q[0])
    return (1e308*t+sum(x*x for x in q),
            [1e308*(1-t*t)+2*q[0], 2*q[1]])


class EnergyOverflow(unittest.TestCase):
    def test_standalone_rejects_overflowed_endpoint_difference(self):
        target = cubic_target(1e308)
        self.assertEqual(target([-1., 0.])[0], -1e308)
        self.assertEqual(target([1., 0.])[0], 1e308)
        with self.assertRaises(ValueError):
            leapfrog(target, [-1., 0.], [2., 0.], 1., 1)
        with self.assertRaises(ValueError):
            leapfrog(target, [1., 0.], [-2., 0.], 1., 1)

    def test_finite_large_differences_keep_both_acceptance_directions(self):
        target = cubic_target(8e307)
        uphill = leapfrog(target, [-1., 0.], [2., 0.], 1., 1)
        downhill = leapfrog(target, [1., 0.], [-2., 0.], 1., 1)
        self.assertEqual(uphill['energy_error'], 1.6e308)
        self.assertEqual(downhill['energy_error'], -1.6e308)
        self.assertFalse(accept(-1., uphill['energy_error']))
        self.assertTrue(accept(-1., downhill['energy_error']))

    def test_random_walk_rejects_instead_of_aborting_or_serializing_infinity(self):
        rng = random.Random(0)
        proposal = [-3.+10*rng.gauss(0., 1.), 10*rng.gauss(0., 1.)]
        self.assertTrue(math.isinf(smooth_target(proposal)[0]-smooth_target([-3., 0.])[0]))
        result = sample(smooth_target, [-3., 0.], method='random_walk', draws=4,
                        warmup=0, step_size=10., seed=0)
        first = result['transitions'][0]
        self.assertTrue(first['invalid_trajectory'])
        self.assertFalse(first['accepted'])
        self.assertIsNone(first['energy_error'])
        self.assertEqual(first['state'], [-3., 0.])
        self.assertEqual(result['potential_gradient_callback_calls'], 5)
        self.assertEqual(len(result['samples']), 4)
        json.dumps(result, allow_nan=False)

    def test_actual_hmc_marks_overflowed_difference_invalid(self):
        momentum = random.Random(0).gauss(0., 1.)
        epsilon = 2/momentum
        # First momentum draw and this duration reach the opposite flat endpoint.
        result = sample(cubic_target(1e308), [-1., 0.], draws=4, warmup=0,
                        step_size=epsilon, steps=1, seed=0)
        first = result['transitions'][0]
        self.assertTrue(first['invalid_trajectory'])
        self.assertFalse(first['accepted'])
        self.assertIsNone(first['energy_error'])
        self.assertEqual(first['state'], [-1., 0.])
        self.assertEqual(len(result['samples']), 4)
        self.assertLessEqual(result['potential_gradient_callback_calls'], 9)
        json.dumps(result, allow_nan=False)


if __name__ == '__main__':
    unittest.main()
