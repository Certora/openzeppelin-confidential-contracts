/*
 * ERC7984ERC20Wrapper: two-step unwrapping. An unwrap request burns the amount, makes it publicly decryptable and
 * records the receiver under the burned amount's handle; the finalization pays `cleartext * rate` underlying once
 * the KMS proof of that handle's decryption is accepted. The rules cover the request, the payout, the revert
 * conditions and the life cycle of a request.
 *
 * A request is `{recipient, metadata}`; the public unwrap functions record `bytes12(0)` as metadata.
 *
 * Model: setup/*.spec. F5: the KMS accepts or rejects a proof (`kmsAccepts`); rules that reason about
 * the amount paid assume an accepted proof certifies `fheVal(id) == cleartext`.
 */
import "setup/invariants.spec";

/// Calls one of the two unwrap overloads: the handle form, or the input-proof form with a non-empty proof.
function doUnwrap(env e, bool handleForm, address from, address to,
                  ERC7984ERC20WrapperHarness.euint64 amount, ERC7984ERC20WrapperHarness.externalEuint64 input, bytes proof) returns bytes32 {
    if (handleForm) {
        return unwrap(e, from, to, amount);
    }
    require proof.length > 0, "setup/transfers.spec: a non-empty proof makes FHE.fromExternal verify the input; an empty one is the handle form";
    return unwrap(e, from, to, input, proof);
}

function doUnwrapWithRevert(env e, bool handleForm, address from, address to,
                            ERC7984ERC20WrapperHarness.euint64 amount, ERC7984ERC20WrapperHarness.externalEuint64 input, bytes proof) returns bool {
    if (handleForm) {
        unwrap@withrevert(e, from, to, amount);
    } else {
        unwrap@withrevert(e, from, to, input, proof);
    }
    return lastReverted;
}

/// Handle of the amount an unwrap request asks for.
function requestedHandle(bool handleForm, ERC7984ERC20WrapperHarness.euint64 amount, ERC7984ERC20WrapperHarness.externalEuint64 input) returns bytes32 {
    return handleForm ? amount : verifiedHandle(input);
}

/// An unwrap request burns exactly the requested amount `x` or nothing (nothing when the balance is insufficient),
/// records the receiver and empty metadata under a fresh non-zero id, makes the burned amount publicly decryptable
/// and moves no underlying. The account whose tokens were burnt is never the zero address.
rule unwrapBurnsAllOrNothingAndRecordsRequest(env e, bool handleForm, address from, address to,
        ERC7984ERC20WrapperHarness.euint64 amount, ERC7984ERC20WrapperHarness.externalEuint64 input, bytes proof, address other) {
    requireBooksInvariants();
    require other != from, "the frame condition is about every account other than the holder";

    mathint x = fheVal(requestedHandle(handleForm, amount, input));
    mathint balFrom = balV(from);
    mathint balOther = balV(other);
    mathint supply = tsV();
    mathint pending = sumPending;
    mathint held = heldByWrapper();
    require outCount == 0, "the log of outgoing underlying transfers (U4) starts empty, so it shows what this call alone sent";

    bytes32 id = doUnwrap(e, handleForm, from, to, amount, input, proof);
    mathint burned = fheVal(id);

    assert burned == (balFrom >= x ? x : 0), "all or nothing";
    assert balV(from) == balFrom - burned;
    assert balV(other) == balOther;
    assert tsV() == supply - burned;
    assert sumPending == pending + burned, "a new request; none is overwritten";
    assert id != to_bytes32(0);
    assert to != 0 && unwrapRequester(id) == to;
    assert requestMetadata(id) == to_bytes12(0), "the public unwrap functions record no metadata";
    assert from != 0, "the burnt account is never the zero address";
    assert aclPublic[id], "the burned amount is publicly decryptable";
    assert heldByWrapper() == held && outCount == 0, "no underlying moves";
}

/// The receiver must not be the zero address.
rule unwrapToZeroReceiverReverts(env e, bool handleForm, address from,
        ERC7984ERC20WrapperHarness.euint64 amount, ERC7984ERC20WrapperHarness.externalEuint64 input, bytes proof) {
    bool reverted = doUnwrapWithRevert(e, handleForm, from, 0, amount, input, proof);
    assert reverted;
}

/// Only the holder or an operator with an unexpired authorization can request an unwrap of the holder's tokens.
rule unwrapRequiresHolderOrLiveOperator(env e, bool handleForm, address from, address to,
        ERC7984ERC20WrapperHarness.euint64 amount, ERC7984ERC20WrapperHarness.externalEuint64 input, bytes proof) {
    require e.msg.sender != from && !isOperator(e, from, e.msg.sender), "the revert condition: the caller is neither the holder nor a live operator of it";
    bool reverted = doUnwrapWithRevert(e, handleForm, from, to, amount, input, proof);
    assert reverted;
}

/// A caller passing an existing encrypted amount must be allowed to use it.
rule unwrapWithHandleRequiresCallerAccess(env e, address from, address to, ERC7984ERC20WrapperHarness.euint64 amount) {
    require !cvlIsAllowed(amount, e.msg.sender), "the revert condition: the caller is not allowed to use the amount handle";
    unwrap@withrevert(e, from, to, amount);
    assert lastReverted;
}

/// Finalizing pays exactly `decrypted_amount * rate` to the receiver recorded at request time, verifies the proof
/// against the request's own handle, and removes the request with its metadata.
rule finalizePaysRecordedReceiverOnce(env e, bytes32 id, uint64 cleartext, bytes proof) {
    requireBooksInvariants();
    require fheVal(id) == to_mathint(cleartext), "F5: an accepted KMS proof certifies the decrypted value of the request's handle";

    address token = underlying();
    mathint r = rate();
    address receiver = unwrapRequester(id);
    require receiver != currentContract, "a request paid to the wrapper itself pays nothing out, which this payment statement excludes";
    mathint receiverHeld = uBal[token][receiver];
    mathint wrapperHeld = uBal[token][currentContract];
    mathint pending = sumPending;
    require outCount == 0 && kmsChecks == 0, "the logs of outgoing transfers (U4) and KMS checks start empty, so they show what this call alone did";

    finalizeUnwrap(e, id, cleartext, proof);

    assert receiver != 0;
    assert to_mathint(uBal[token][receiver]) == receiverHeld + cleartext * r;
    assert to_mathint(uBal[token][currentContract]) == wrapperHeld - cleartext * r;
    assert outCount == 1 && lastOutTo == receiver && lastOutAmount == cleartext * r;
    assert kmsChecks == 1 && kmsCheckedHandle == id, "the proof is checked against this request's handle";
    assert unwrapRequester(id) == 0 && requestMetadata(id) == to_bytes12(0);
    assert sumPending == pending - cleartext;
}

/// Finalization fails without an accepted decryption proof.
rule finalizeRequiresAcceptedProof(env e, bytes32 id, uint64 cleartext, bytes proof) {
    require !kmsAccepts[id], "the revert condition (F5): the KMS rejects the proof";
    finalizeUnwrap@withrevert(e, id, cleartext, proof);
    assert lastReverted;
}

/// Finalizing a request that does not exist fails.
rule finalizeUnknownRequestReverts(env e, bytes32 id, uint64 cleartext, bytes proof) {
    require unwrapRequester(id) == 0, "the revert condition: there is no such request";
    finalizeUnwrap@withrevert(e, id, cleartext, proof);
    assert lastReverted;
}

/// A second finalization of the same request fails.
rule finalizeTwiceReverts(env e1, env e2, bytes32 id, uint64 cleartext1, uint64 cleartext2, bytes proof1, bytes proof2) {
    finalizeUnwrap(e1, id, cleartext1, proof1);
    finalizeUnwrap@withrevert(e2, id, cleartext2, proof2);
    assert lastReverted;
}

/// Whoever calls it, finalization has the same outcome.
rule finalizeOutcomeIndependentOfCaller(env e1, env e2, bytes32 id, uint64 cleartext, bytes proof) {
    require e1.block.timestamp == e2.block.timestamp && e1.block.number == e2.block.number, "the two calls differ in the caller only, so they are in the same block";
    require e1.msg.value == e2.msg.value, "the two calls differ in the caller only: the same value, so a non-payable revert is the same in both";

    address token = underlying();
    address receiver = unwrapRequester(id);
    storage initial = lastStorage;

    finalizeUnwrap@withrevert(e1, id, cleartext, proof);
    bool reverted1 = lastReverted;
    mathint receiverHeld1 = uBal[token][receiver];
    mathint wrapperHeld1 = heldByWrapper();
    address requester1 = unwrapRequester(id);

    finalizeUnwrap@withrevert(e2, id, cleartext, proof) at initial;
    bool reverted2 = lastReverted;

    assert reverted1 == reverted2;
    assert !reverted1 => (to_mathint(uBal[token][receiver]) == receiverHeld1
                          && heldByWrapper() == wrapperHeld1
                          && unwrapRequester(id) == requester1);
}

/// A request is created only by an unwrap request and removed only by its finalization; while pending, its receiver
/// and metadata never change (so a request is never overwritten).
rule requestsChangeOnlyByUnwrapAndFinalize(env e, method f, calldataarg args, bytes32 id) filtered {
    f -> !f.isView
} {
    address receiverBefore = unwrapRequester(id);
    bytes12 metadataBefore = requestMetadata(id);

    f(e, args);

    address receiverAfter = unwrapRequester(id);
    assert receiverBefore == 0 && receiverAfter != 0 => isUnwrapEntry(f);
    assert receiverBefore != 0 && receiverAfter == 0 => isFinalize(f);
    assert receiverBefore != 0 && receiverAfter != 0 =>
        (receiverAfter == receiverBefore && requestMetadata(id) == metadataBefore);
    assert requestMetadata(id) != metadataBefore => (isUnwrapEntry(f) || isFinalize(f));
}

/// A pending request with an accepted proof can always be finalized, and it pays the original amount
/// (finalizePaysRecordedReceiverOnce).
rule pendingRequestIsFinalizable(env e, bytes32 id, uint64 cleartext, bytes proof) {
    requireBooksInvariants();
    require e.msg.value == 0, "finalizeUnwrap is non-payable and the rule asserts that it does not revert";

    address receiver = unwrapRequester(id);
    require receiver != 0, "the property is about a pending request";
    require fheVal(id) == to_mathint(cleartext) && kmsAccepts[id], "the property is about an accepted proof, and F5: an accepted proof certifies the decrypted value of the request's handle";
    require !uTokenRejects, "U2: the underlying token accepts the payout";
    require to_mathint(uBal[underlying()][receiver]) + cleartext * rate() <= max_uint256, "U2: a credit that overflows the receiver's balance reverts, as in a standard ERC-20";

    finalizeUnwrap@withrevert(e, id, cleartext, proof);

    assert !lastReverted;
}
