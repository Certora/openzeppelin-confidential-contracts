/*
 * ERC7984ERC20Wrapper: backing and supply.
 *
 * The underlying held by the wrapper covers every confidential token in circulation and every pending unwrap
 * request, at the fixed rate (wrapperIsSolvent, with the other invariants of setup/invariants.spec, all proved
 * here). The rules show that only a direct transfer of underlying changes the surplus beyond that backing, that
 * such a transfer does not affect the confidential books, that the supply moves only by wraps and unwrap requests,
 * and that underlying leaves the wrapper only through finalization and the remainder refund of a callback wrap.
 * The exact amounts of each operation are in wrap.spec and unwrap.spec.
 *
 * Model: setup/*.spec (assumptions F1-F5, U1-U6, L1, R1).
 */
import "setup/invariants.spec";

use invariant totalSupplyIsSumOfBalances;
use invariant zeroAddressHoldsNothing;
use invariant rateIsPositive;
use invariant pendingSumIsNonNegative;
use invariant wrapperIsSolvent;

/// Every wrapper operation leaves the surplus `held - rate * (supply + pending)` unchanged. The callback wrap is the
/// one exception, see below.
rule surplusUnchangedByWrapperOperations(env e, method f, calldataarg args) filtered {
    f -> !f.isView && !isCallbackWrap(f)
} {
    requireBooksInvariants();
    require e.msg.sender != currentContract,
        "the wrapper never calls its own entry points; as its own depositor its wrap minted without taking tokens";

    mathint before = surplus();

    if (isFinalize(f)) {
        bytes32 id; uint64 cleartext; bytes proof;
        require fheVal(id) == to_mathint(cleartext), "F5: an accepted KMS proof certifies the decrypted value of the request's handle";
        // A request whose receiver is the wrapper itself pays nothing out: its finalization turns the
        // burned amount into a direct transfer.
        require unwrapRequester(id) != currentContract, "a request paid to the wrapper itself is a direct transfer, which the property excludes";
        finalizeUnwrap(e, id, cleartext, proof);
    } else {
        f(e, args);
    }

    assert surplus() == before, "only a direct transfer to the wrapper changes the surplus";
}

/// A callback wrap consumes exactly the `amount` the token delivered just before calling back, so it leaves the
/// pre-delivery surplus unchanged. The delivery is the rule's hypothesis: the wrapper mints without checking that the
/// tokens arrived, so a token that calls back without paying is outside this rule.
rule callbackWrapConsumesDeliveredAmount(env e, address operator, address from, uint256 amount, bytes data) {
    requireBooksInvariants();
    require from != currentContract, "the wrapper never calls transferAndCall on its own underlying, so it is not the sender of an ERC-1363 callback";

    mathint before = surplus();
    require before >= to_mathint(amount), "rule hypothesis: the token delivered `amount` before calling back, as ERC-1363 does";

    onTransferReceived(e, operator, from, amount, data);

    assert surplus() == before - amount;
}

/// A direct transfer of underlying to the wrapper changes no confidential balance, the supply or any pending request.
/// Stated as: from the same state, with or without `d` extra underlying held by the wrapper, a successful wrapper
/// operation makes the same changes to the books.
rule directTransfersDoNotAffectBooks(env e, method f, calldataarg args, uint256 d, address a, bytes32 id) filtered {
    f -> !f.isView
} {
    requireBooksInvariants();
    address token = underlying();
    require to_mathint(uBal[token][currentContract]) + d <= max_uint256, "the direct transfer of d underlying must be possible: a token balance cannot exceed 2^256 - 1";

    storage initial = lastStorage;

    f(e, args);
    bytes32 balWithout = balHandle(a);
    bytes32 supplyWithout = tsHandle();
    address requesterWithout = requesterOf(id);

    uint256 unused = rate() at initial;
    addToWrapperHolding(token, d);
    f(e, args);

    assert balHandle(a) == balWithout;
    assert tsHandle() == supplyWithout;
    assert requesterOf(id) == requesterWithout;
}

function addToWrapperHolding(address token, uint256 d) {
    uBal[token][currentContract] = require_uint256(uBal[token][currentContract] + d);
}

/// The public supply estimate `underlying_held / rate` is at least the actual supply. Stays a rule: its only requires
/// are the proved books invariants, so it is their corollary. As an invariant, its step would have to re-prove
/// solvency and the non-negative pending sum after the call, which a step cannot take from the invariants of the
/// state before it.
rule inferredTotalSupplyIsAtLeastSupply() {
    requireBooksInvariants();
    assert to_mathint(inferredTotalSupply()) >= tsV();
}

/// The supply increases only by wrapping and decreases only by unwrap requests; transfers never change it.
rule supplyMovesOnlyByWrapAndUnwrapRequest(env e, method f, calldataarg args) filtered {
    f -> !f.isView
} {
    requireBooksInvariants();

    mathint before = tsV();
    f(e, args);

    assert tsV() > before => isWrapEntry(f);
    assert tsV() < before => isUnwrapEntry(f);
}

/// Underlying leaves the wrapper only through unwrap finalization and the remainder refund of a callback wrap, at
/// most once per call.
rule underlyingLeavesOnlyByFinalizeOrRefund(env e, method f, calldataarg args) filtered {
    f -> !f.isView
} {
    requireBooksInvariants();
    require outCount == 0, "the log of outgoing underlying transfers (U4) starts empty, so it shows what this call alone sent";
    require e.msg.sender != currentContract,
        "the wrapper never calls its own entry points; as its own depositor its wrap logged a transfer out";

    mathint heldBefore = heldByWrapper();
    f(e, args);

    assert outCount > 0 => (isFinalize(f) || isCallbackWrap(f));
    assert outCount <= 1;
    assert heldByWrapper() < heldBefore => (isFinalize(f) || isCallbackWrap(f));
}

/// The wrapper never grants anyone an allowance over its underlying.
rule wrapperNeverGrantsAllowance(env e, method f, calldataarg args) filtered {
    f -> !f.isView
} {
    mathint before = approveCalls;
    f(e, args);
    assert approveCalls == before;
}
