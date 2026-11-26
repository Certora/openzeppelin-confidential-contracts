/*
 * ERC7984ERC20Wrapper: token parameters. The underlying token, the decimals and the rate are immutables, set by the
 * constructor; the rules cover what the constructor derives, that the parameters never change, and the ERC-165
 * interfaces the wrapper reports.
 *
 * A rule cannot call the constructor, so what it derives is an invariant: the base case of an invariant runs the
 * constructor, and the immutables never change after it.
 *
 * The constructor's `decimals()` query to the token is a `staticcall` that the Prover cannot resolve in constructor
 * code, so it havocs the answer: every answer, a failure and a malformed reply are all possible, but CVL cannot see
 * which one the constructor got. The invariant is therefore stated over the outcomes the constructor can produce,
 * not over the token's actual answer.
 *
 * Model: setup/*.spec.
 */
import "setup/invariants.spec";

methods {
    function supportsInterface(bytes4) external returns (bool) envfree;
}

/// `r` is 10^k for some k from 1 to 77. 10^77 is the largest power of ten below 2^256, so `10 ** (d - 6)` with a
/// larger exponent reverts in the constructor.
definition isPowerOfTenAboveOne(mathint r) returns bool =
    r == 10^1
    || r == 10^2
    || r == 10^3
    || r == 10^4
    || r == 10^5
    || r == 10^6
    || r == 10^7
    || r == 10^8
    || r == 10^9
    || r == 10^10
    || r == 10^11
    || r == 10^12
    || r == 10^13
    || r == 10^14
    || r == 10^15
    || r == 10^16
    || r == 10^17
    || r == 10^18
    || r == 10^19
    || r == 10^20
    || r == 10^21
    || r == 10^22
    || r == 10^23
    || r == 10^24
    || r == 10^25
    || r == 10^26
    || r == 10^27
    || r == 10^28
    || r == 10^29
    || r == 10^30
    || r == 10^31
    || r == 10^32
    || r == 10^33
    || r == 10^34
    || r == 10^35
    || r == 10^36
    || r == 10^37
    || r == 10^38
    || r == 10^39
    || r == 10^40
    || r == 10^41
    || r == 10^42
    || r == 10^43
    || r == 10^44
    || r == 10^45
    || r == 10^46
    || r == 10^47
    || r == 10^48
    || r == 10^49
    || r == 10^50
    || r == 10^51
    || r == 10^52
    || r == 10^53
    || r == 10^54
    || r == 10^55
    || r == 10^56
    || r == 10^57
    || r == 10^58
    || r == 10^59
    || r == 10^60
    || r == 10^61
    || r == 10^62
    || r == 10^63
    || r == 10^64
    || r == 10^65
    || r == 10^66
    || r == 10^67
    || r == 10^68
    || r == 10^69
    || r == 10^70
    || r == 10^71
    || r == 10^72
    || r == 10^73
    || r == 10^74
    || r == 10^75
    || r == 10^76
    || r == 10^77;

/// The constructor derives decimals and rate from the underlying's decimals `d` (18 when they cannot be read): more
/// than 6 decimals gives decimals 6 and `rate = 10^(d - 6)`, otherwise decimals `d` and rate 1. Stated over the
/// outcomes, for every answer of the token: either the rate is 1 and the decimals are at most 6, or the decimals are
/// 6 and the rate is a power of ten above 1.
invariant constructorDerivesDecimalsAndRate()
    (rate() == 1 && decimals() <= 6) || (decimals() == 6 && isPowerOfTenAboveOne(to_mathint(rate())));

/// The underlying token, the decimals and the rate never change.
rule tokenParametersNeverChange(env e, method f, calldataarg args) filtered {
    f -> !f.isView
} {
    address token = underlying();
    uint8 d = decimals();
    uint256 r = rate();

    f(e, args);

    assert underlying() == token && decimals() == d && rate() == r;
}

/// The wrapper advertises the confidential token, confidential wrapper and token-callback receiver interfaces (and
/// ERC-165 itself), and denies 0xffffffff, as ERC-165 requires. `supportsInterface` reads no state, so the condition
/// holds in every state and the invariant's `invariant_not_trivial_postcondition` sanity check fails by construction:
/// run it with `--rule_sanity none`.
invariant advertisesTokenWrapperAndReceiverInterfaces()
    supportsInterface(helper.erc7984InterfaceId())
    && supportsInterface(helper.erc7984ERC20WrapperInterfaceId())
    && supportsInterface(helper.erc1363ReceiverInterfaceId())
    && supportsInterface(helper.erc165InterfaceId())
    && !supportsInterface(to_bytes4(0xffffffff));
