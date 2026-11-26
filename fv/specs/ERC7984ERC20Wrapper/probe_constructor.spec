/*
 * Probe, not a property: the constructor can produce the outcomes that params.spec::constructorDerivesDecimalsAndRate
 * covers (decimals 6 with rate 10^12, and decimals 2 with rate 1). Each invariant is expected VIOLATED in the base
 * case, where the constructor produces the outcome the invariant denies. A rule cannot call the constructor, so
 * these take the place of `satisfy` witnesses.
 *
 * The constructor's `decimals()` query is not dispatched to the mock: the Prover cannot resolve it in constructor
 * code and havocs its answer. So the mock's fields do not decide the outcome; the antecedents about them only name
 * the case.
 */
import "setup/invariants.spec";

using UnderlyingDecimalsMock as decimalsMock;

methods {
    function decimalsMock.value() external returns (uint8) envfree;
    function decimalsMock.reverts() external returns (bool) envfree;
    function _.decimals() external => DISPATCHER(true);
}

/// Expected VIOLATED: a token whose `decimals()` reverts gets the 18-decimal fallback (decimals 6, rate 10^12).
invariant probeFallbackIsUnreachable()
    (underlying() == decimalsMock && decimalsMock.reverts()) => !(decimals() == 6 && to_mathint(rate()) == 10^12);

/// Expected VIOLATED: a token with 2 decimals keeps them and gets rate 1.
invariant probeSmallDecimalsAreUnreachable()
    (underlying() == decimalsMock && !decimalsMock.reverts() && decimalsMock.value() == 2) => !(decimals() == 2 && rate() == 1);
