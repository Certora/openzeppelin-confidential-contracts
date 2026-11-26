/*
 * State invariants of ERC7984ERC20Wrapper. They are proved in solvency.spec (`use invariant`) and imported by the
 * other specs only so that rules can `requireInvariant` them.
 *
 * The wrapper is not upgradeable: the token parameters are immutables set by the constructor, which is the base
 * case of every invariant.
 */
import "base.spec";

/// The confidential total supply equals the sum of all confidential balances.
invariant totalSupplyIsSumOfBalances()
    tsV() == sumBalances;

/// The zero address never holds a balance.
invariant zeroAddressHoldsNothing()
    balV(0) == 0;

/// The rate is positive. The constructor sets it to 1 or a power of ten, and it is an immutable.
invariant rateIsPositive()
    rate() > 0;

/// The amount held by pending unwrap requests is never negative.
invariant pendingSumIsNonNegative()
    sumPending >= 0;

/// The underlying held by the wrapper covers, at the fixed rate, every confidential token in circulation plus every
/// unwrap request not finalized yet.
invariant wrapperIsSolvent()
    heldByWrapper() >= rate() * (tsV() + sumPending)
    {
        preserved with (env e) {
            // a wrap by the wrapper itself would move no underlying (from == to) and still mint
            require e.msg.sender != currentContract, "the wrapper never calls its own entry points (no `this.` call in ERC7984 or ERC7984ERC20Wrapper), so it is never msg.sender of one";
            require underlying() != currentContract, "U6: the underlying is a real token, not the wrapper";
            requireInvariant totalSupplyIsSumOfBalances();
        }
        preserved onTransferReceived(address operator, address from, uint256 amount, bytes data) with (env e) {
            require underlying() != currentContract, "U6: the underlying is a real token, not the wrapper";
            requireInvariant totalSupplyIsSumOfBalances();
            requireInvariant pendingSumIsNonNegative();
            // Without it the token can call back without paying, and the wrapper mints anyway: the wrapper does not
            // check that the tokens arrived.
            require surplus() >= to_mathint(amount),
                "the token credits the wrapper with amount before calling back, as ERC-1363 does";
        }
        preserved finalizeUnwrap(bytes32 id, uint64 cleartext, bytes proof) with (env e) {
            require underlying() != currentContract, "U6: the underlying is a real token, not the wrapper";
            requireInvariant totalSupplyIsSumOfBalances();
            require fheVal(id) == to_mathint(cleartext),
                "F5: an accepted KMS proof certifies the decrypted value of the request's handle";
        }
    }

/// The underlying surplus: what the wrapper holds beyond the backing of supply and pending unwraps.
function surplus() returns mathint {
    return heldByWrapper() - rate() * (tsV() + sumPending);
}

function requireBooksInvariants() {
    requireInvariant totalSupplyIsSumOfBalances();
    requireInvariant zeroAddressHoldsNothing();
    requireInvariant rateIsPositive();
    requireInvariant pendingSumIsNonNegative();
    requireInvariant wrapperIsSolvent();
}
