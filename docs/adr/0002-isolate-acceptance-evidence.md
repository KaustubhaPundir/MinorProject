# Separate repair feedback from final acceptance evidence

A generator that sees every validation case can adapt to those cases without demonstrating broader compatibility. We chose visible regression feedback and a protected held-out evaluation after a candidate is frozen, accepting the additional harness complexity. Any held-out failure ends the run; once revealed, it becomes regression evidence and subsequent acceptance uses a fresh suite.
