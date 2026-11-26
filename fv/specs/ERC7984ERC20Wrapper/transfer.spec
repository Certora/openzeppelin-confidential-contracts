/*
 * ERC7984ERC20Wrapper: confidential transfers, value and authorization. The rules cover what a transfer moves and
 * between whom, that it neither mints nor burns, that whether it succeeds does not depend on encrypted values, and
 * who may move a holder's balance and change its operator entries. Transfers with a callback are in callback.spec,
 * the ACL permissions and the authorization checks of the entry points in acl.spec, and the mint and burn sides
 * in wrap.spec, unwrap.spec and solvency.spec.
 *
 * Model: setup/*.spec. The eight transfer entry points (four kinds, each with and without a memo) are called
 * through setup/transfers.spec. The value rules hold for the transfer-and-call variants under R1: the receiver
 * spends nothing in its callback. A receiver that does is the best-effort refund that ERC7984 documents; the
 * model cannot express it, so no rule here or in callback.spec states what happens then.
 *
 * Each liveness rule fixes the public conditions and leaves every encrypted value (balances, amounts)
 * free; not reverting for all of them is independence from the secrets.
 */
import "setup/invariants.spec";
import "setup/transfers.spec";

/// When every public condition holds (non-zero recipient, and the amount is either a verified input or an existing
/// handle the caller may use), a transfer does not fail, whatever the balances and amount; an insufficient balance
/// moves nothing instead. ERC7984 has no transfer that takes a handle argument; an empty input proof makes
/// `FHE.fromExternal` use the input as an existing handle.
rule transferDoesNotDependOnSecrets(env e, address to, ERC7984ERC20WrapperHarness.externalEuint64 input, bytes proof) {
    requireBooksInvariants();
    require e.msg.value == 0, "confidentialTransfer is non-payable and the rule asserts that it does not revert";
    require e.msg.sender != 0, "chain fact: no transaction has the zero address as sender, and ERC-7984 rejects it as the sender of a transfer";
    require to != 0, "public condition of the property: a non-zero recipient";
    require proof.length > 0 || cvlIsAllowed(input, e.msg.sender), "public condition of the property: the input is verified, or the caller may use it as an existing handle";

    confidentialTransfer@withrevert(e, to, input, proof);

    assert !lastReverted;
}

/// The same for a transfer by an authorized operator.
rule transferFromDoesNotDependOnSecrets(env e, address from, address to, ERC7984ERC20WrapperHarness.externalEuint64 input, bytes proof) {
    requireBooksInvariants();
    require e.msg.value == 0, "confidentialTransferFrom is non-payable and the rule asserts that it does not revert";
    require from != 0 && to != 0, "public condition of the property: ERC-7984 rejects the zero address as sender or recipient";
    require isOperator(e, from, e.msg.sender), "public condition of the property: the caller is an authorized operator of the sender";
    require proof.length > 0 || cvlIsAllowed(input, e.msg.sender), "public condition of the property: the input is verified, or the caller may use it as an existing handle";

    confidentialTransferFrom@withrevert(e, from, to, input, proof);

    assert !lastReverted;
}

/// A transfer lowers the sender's balance and raises the recipient's by exactly the amount it returns, so the credit
/// never wraps around. For the transfer-and-call variants the returned amount is the net `sent - refund`: a call that
/// reports 0 leaves both balances as they were, and the net amount is the recipient's gain. R1 applies: the receiver
/// spends nothing in its callback.
rule transferConservesValueBetweenParties(env e, uint8 variant, address from, address to,
        ERC7984ERC20WrapperHarness.externalEuint64 input, bytes proof, bytes data, bytes32 memo) {
    requireBooksInvariants();
    require from != to, "the property is about two distinct parties; a self transfer is selfTransferIsValuePreserving";

    mathint balFrom = balV(from);
    mathint balTo = balV(to);

    ERC7984ERC20WrapperHarness.euint64 moved = transferCall(e, variant, from, to, input, proof, data, memo);

    assert balV(from) == balFrom - fheVal(moved), "the sender loses exactly the amount moved";
    assert balV(to) == balTo + fheVal(moved), "the recipient gains exactly the amount moved";
}

/// A request for more than the sender holds moves nothing: it returns 0 and changes neither balance. (It does not
/// revert: transferDoesNotDependOnSecrets.)
rule insufficientBalanceTransfersZero(env e, uint8 variant, address from, address to,
        ERC7984ERC20WrapperHarness.externalEuint64 input, bytes proof, bytes data, bytes32 memo) {
    requireBooksInvariants();

    require proof.length > 0, "setup/transfers.spec: the input forms verify the input, so the amount is `verifiedHandle(input)`";
    mathint requested = fheVal(transferAmountHandle(input));
    mathint balFrom = balV(from);
    mathint balTo = balV(to);
    require requested > balFrom, "the property is about a request for more than the sender holds";

    ERC7984ERC20WrapperHarness.euint64 moved = transferCall(e, variant, from, to, input, proof, data, memo);

    assert fheVal(moved) == 0, "an unaffordable transfer reports 0";
    assert balV(from) == balFrom, "the sender's balance is untouched";
    assert balV(to) == balTo, "the recipient's balance is untouched";
}

/// A request the sender can afford moves the full amount (the entry points without a callback; for the
/// transfer-and-call variants: callback.spec, andCallHookAmountIsActuallyTransferred).
rule sufficientBalanceTransferMovesFullAmount(env e, uint8 variant, address from, address to,
        ERC7984ERC20WrapperHarness.externalEuint64 input, bytes proof, bytes data, bytes32 memo) {
    requireBooksInvariants();
    require from != to, "the property is about two distinct parties; a self transfer is selfTransferIsValuePreserving";
    require variant <= 3, "the property is about the entry points without a callback (variants 0 to 3 of setup/transfers.spec)";

    require proof.length > 0, "setup/transfers.spec: the input forms verify the input, so the amount is `verifiedHandle(input)`";
    mathint requested = fheVal(transferAmountHandle(input));
    mathint balFrom = balV(from);
    mathint balTo = balV(to);
    require requested <= balFrom, "the property is about a request the sender can afford";

    ERC7984ERC20WrapperHarness.euint64 moved = transferCall(e, variant, from, to, input, proof, data, memo);

    assert fheVal(moved) == requested, "the full requested amount is reported as moved";
    assert balV(from) == balFrom - requested, "the sender is debited the full amount";
    assert balV(to) == balTo + requested, "the recipient is credited the full amount";
}

/// A transfer from an account to itself leaves its balance as it was.
rule selfTransferIsValuePreserving(env e, uint8 variant, address from,
        ERC7984ERC20WrapperHarness.externalEuint64 input, bytes proof, bytes data, bytes32 memo) {
    requireBooksInvariants();

    mathint balBefore = balV(from);

    transferCall(e, variant, from, from, input, proof, data, memo);

    assert balV(from) == balBefore, "the debit and the credit cancel out";
}

/// A transfer writes no balance other than the sender's and the recipient's (the refund leg of a transfer-and-call
/// included).
rule uninvolvedBalancesUnchanged(env e, uint8 variant, address from, address to, address other,
        ERC7984ERC20WrapperHarness.externalEuint64 input, bytes proof, bytes data, bytes32 memo) {
    require other != from && other != to, "the property is about an account that is neither the sender nor the recipient";

    bytes32 handleBefore = balHandle(other);

    transferCall(e, variant, from, to, input, proof, data, memo);

    assert balHandle(other) == handleBefore, "no balance of a non-party is written";
}

/// A transfer entry point rejects the zero address on either side, so it can neither mint nor burn, and a successful
/// transfer leaves the total supply unchanged.
rule publicTransferEntrypointsCannotMintOrBurn(env e, uint8 variant, address from, address to,
        ERC7984ERC20WrapperHarness.externalEuint64 input, bytes proof, bytes data, bytes32 memo) {
    requireBooksInvariants();

    mathint supply = tsV();

    bool reverted = transferReverts(e, variant, from, to, input, proof, data, memo);

    assert (from == 0 || to == 0) => reverted, "the zero address is rejected on either side";
    assert !reverted => tsV() == supply, "a transfer does not change the total supply";
}

/// Only a holder grants, changes or revokes its own operator authorizations.
rule operatorEntriesChangeOnlyByTheirHolder(env e, method f, calldataarg args, address holder, address spender) filtered {
    f -> !f.isView
} {
    mathint before = operatorUntil(holder, spender);
    f(e, args);
    assert operatorUntil(holder, spender) != before =>
        (e.msg.sender == holder && f.selector == sig:setOperator(address, uint48).selector);
}

/// `setOperator` fails exactly when the operator is the zero address or the caller itself. Otherwise it sets the
/// caller's entry for the operator to the given expiry, and it changes no other operator entry.
rule setOperatorEffects(env e, address spender, uint48 until, address holder, address other) {
    require e.msg.value == 0, "setOperator is non-payable and the rule states exactly when it reverts";
    mathint otherBefore = operatorUntil(holder, other);

    setOperator@withrevert(e, spender, until);
    bool reverted = lastReverted;

    assert reverted <=> (spender == 0 || spender == e.msg.sender), "only the zero address and the caller itself are rejected as operators";
    assert !reverted => operatorUntil(e.msg.sender, spender) == to_mathint(until);
    assert (holder != e.msg.sender || other != spender) => operatorUntil(holder, other) == otherBefore;
}

/// A confidential balance decreases only through an action of its holder or of an operator whose authorization has
/// not expired.
rule balanceDecreasesOnlyThroughHolderOrOperator(env e, method f, calldataarg args, address a) filtered {
    f -> !f.isView
} {
    requireBooksInvariants();

    bool authorized = e.msg.sender == a || isOperator(e, a, e.msg.sender);
    mathint before = balV(a);

    f(e, args);

    assert balV(a) < before => authorized;
}
