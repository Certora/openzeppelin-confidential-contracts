/*
 * ERC7984ERC20Wrapper: transfer with callback (confidentialTransferAndCall, confidentialTransferFromAndCall): the
 * amount handed to the receiver, the refund, what counts as acceptance, the receiver's permissions when its hook
 * runs, and transfers to the wrapper's own address. The net amount and the balances after a refund are in
 * transfer.spec (transferConservesValueBetweenParties).
 *
 * `_transferAndCall` builds its result as `FHE.sub(sent, refund)`, so the handle provenance of setup/fhe.spec
 * (`hOp`, `hA`, `hB`, `hC`) lets a rule name the ciphertexts the contract never stores. For the returned `net`:
 *      hA(net)             = sent     the amount handed to the receiver's hook
 *      hB(net)             = refund   what the refund leg took back
 *      hB(hB(net))         = FHE.select(retval, 0, sent)    the refund request
 *      hA(hB(hB(net)))     = the acceptance control actually fed to that select
 *
 * Model: setup/*.spec, with R1: the receiver's hook either reverts or answers an arbitrary ebool, and changes
 * no state. The documented best-effort refund (a receiver that spends or burns the amount inside its hook and
 * answers false, so the refund moves 0) is therefore outside every rule here: no rule can say what the sender
 * ends up with in that case. The hook's `amount` is the one argument the model passes on (`receiverAnswer(to,
 * amount)`); its `operator`, `from` and `data` are not observable.
 */
import "setup/invariants.spec";
import "setup/transfers.spec";

/// The refund is either zero or the full amount sent, so never more than was sent, and the net amount returned is
/// `sent - refund` without underflow.
rule andcallRefundBoundedByAmountCredited(env e, uint8 variant, address from, address to,
        ERC7984ERC20WrapperHarness.externalEuint64 input, bytes proof, bytes data, bytes32 memo) {
    requireBooksInvariants();
    require isAndCallVariant(variant), "the property: the transfer-and-call variants";
    require from != 0 && to != 0, "the property: a transfer between two accounts (a transfer with the zero address as a party reverts)";

    ERC7984ERC20WrapperHarness.euint64 net = transferCall(e, variant, from, to, input, proof, data, memo);
    mathint sent = fheVal(hA(net));
    mathint refund = fheVal(hB(net));

    assert refund <= sent, "the refund leg never takes back more than was sent";
    assert fheVal(net) == sent - refund, "`sent - refund` does not underflow";
    assert refund == 0 || refund == sent, "the refund is all or nothing";
}

/// The amount handed to the receiver is the amount the forward leg actually moved, never the larger amount that was
/// requested: `sent == (requested <= balance(from) ? requested : 0)`. A contract receiver is handed exactly that
/// `sent` handle: its answer for it is the acceptance control of the refund request.
rule andCallHookAmountIsActuallyTransferred(env e, uint8 variant, address from, address to,
        ERC7984ERC20WrapperHarness.externalEuint64 input, bytes proof, bytes data, bytes32 memo) {
    requireBooksInvariants();
    require isAndCallVariant(variant), "the property: the transfer-and-call variants";
    require from != 0 && to != 0 && from != to, "the property: a transfer between two distinct accounts (a transfer with the zero address as a party reverts)";

    require proof.length > 0, "the input forms verify the input, so the amount is `verifiedHandle(input)` (setup/transfers.spec)";
    mathint requested = fheVal(transferAmountHandle(input));
    mathint balFrom = balV(from);

    ERC7984ERC20WrapperHarness.euint64 net = transferCall(e, variant, from, to, input, proof, data, memo);
    bytes32 sent = hA(net);

    assert fheVal(sent) == (requested <= balFrom ? requested : 0), "the hook is told the amount moved, not the amount requested";
    assert (nativeCodesize[to] != 0 && receiverAnswer(to, sent) != ZEROH())
        => hA(hB(hB(net))) == receiverAnswer(to, sent), "the receiver is handed the `sent` handle";
}

/// A recipient without code is never called and accepts unconditionally: nothing is refunded and the net amount is
/// the whole forward leg.
rule andCallEoaReceiverAcceptsUnconditionally(env e, uint8 variant, address from, address to,
        ERC7984ERC20WrapperHarness.externalEuint64 input, bytes proof, bytes data, bytes32 memo) {
    requireBooksInvariants();
    require isAndCallVariant(variant), "the property: the transfer-and-call variants";
    require from != 0 && to != 0 && from != to, "the property: a transfer between two distinct accounts (a transfer with the zero address as a party reverts)";
    require nativeCodesize[to] == 0, "the property: a recipient without code";

    ERC7984ERC20WrapperHarness.euint64 net = transferCall(e, variant, from, to, input, proof, data, memo);

    assert fheVal(hB(net)) == 0, "no refund is taken from a recipient without code";
    assert fheVal(net) == fheVal(hA(net)), "such a recipient accepts the whole forward leg";
}

/// The recipient keeps value only if the acceptance control of the refund request decrypts to true and the recipient
/// may use it; an uninitialized, false or foreign answer ends in a full refund (or a revert). The second assertion
/// states the stricter of two readings: that only an answer the recipient may use counts as acceptance, not any
/// handle that decrypts to true.
rule receiverAcceptanceSignalFailsClosed(env e, uint8 variant, address from, address to,
        ERC7984ERC20WrapperHarness.externalEuint64 input, bytes proof, bytes data, bytes32 memo) {
    requireBooksInvariants();
    require isAndCallVariant(variant), "the property: the transfer-and-call variants";
    require from != 0 && to != 0 && from != to, "the property: a transfer between two distinct accounts (a transfer with the zero address as a party reverts)";
    require nativeCodesize[to] != 0, "the property: a recipient with code, so its hook runs";

    ERC7984ERC20WrapperHarness.euint64 net = transferCall(e, variant, from, to, input, proof, data, memo);
    bytes32 acceptance = hA(hB(hB(net)));

    assert fheVal(net) != 0 => fheVal(acceptance) != 0, "value is kept only on an answer that decrypts to true";
    assert fheVal(net) != 0 => cvlIsAllowed(acceptance, to), "value is kept only on an answer the recipient may use";
}

/// When a contract receiver's hook runs, the recipient already holds a persistent allowance on the amount handed to
/// it and on its own balance handle right after the forward credit. The ACL never revokes a permission, and the
/// forward leg runs before the hook, so holding it at the end of the transaction means holding it when the hook ran.
rule receiverHookAmountPreauthorizedForReceiver(env e, uint8 variant, address from, address to,
        ERC7984ERC20WrapperHarness.externalEuint64 input, bytes proof, bytes data, bytes32 memo) {
    requireBooksInvariants();
    require isAndCallVariant(variant), "the property: the transfer-and-call variants";
    require from != 0 && to != 0 && from != to, "the property: a transfer between two distinct accounts (a transfer with the zero address as a party reverts)";
    require nativeCodesize[to] != 0, "the property: a recipient with code, so its hook runs";

    bytes32 balToBefore = balHandle(to);

    ERC7984ERC20WrapperHarness.euint64 net = transferCall(e, variant, from, to, input, proof, data, memo);

    bytes32 sent = hA(net);
    // FHE.add reads an uninitialized balance as the trivial encryption of 0
    bytes32 credited = balToBefore == ZEROH() ? fheTrivH(0) : balToBefore;
    bytes32 balToAfterCredit = fheOpH(OP_ADD(), credited, sent, ZEROH());

    assert aclPersist[sent][to], "the recipient may use the amount before its hook runs";
    assert aclPersist[balToAfterCredit][to], "the recipient may use its post-credit balance before its hook runs";
}

/// A transfer can leave two accounts with the same stored non-zero balance handle, which they did not share before.
/// So distinct accounts do not always have distinct balance handles: a handle is a deterministic function of the
/// operation and its operands (F2), so identical computations on identical operands end in the same handle, for
/// instance every account that never held tokens is given the same encryption of 0. What matters is who may use a
/// balance handle: see acl.spec, storedBalanceHandlesRemainAclAccessible and noCrossAccountBalanceAclGrants.
rule accountsCanShareBalanceHandle(env e, uint8 variant, address from, address to, address x, address y,
        ERC7984ERC20WrapperHarness.externalEuint64 input, bytes proof, bytes data, bytes32 memo) {
    requireBooksInvariants();
    require x != y && x != 0 && y != 0, "the witness: two distinct accounts";
    require !(balHandle(x) != ZEROH() && balHandle(x) == balHandle(y)), "the witness: they do not share a non-zero balance handle before the transfer";

    transferCall(e, variant, from, to, input, proof, data, memo);

    satisfy balHandle(x) != ZEROH() && balHandle(x) == balHandle(y);
}

/// A confidential transfer cannot leave a non-zero balance on the wrapper's own address: the wrapper has no way to
/// move its own confidential balance, so tokens sent there could never move again.
rule transferToTokenContractStrandsCollateral(env e, uint8 variant, address from, address to,
        ERC7984ERC20WrapperHarness.externalEuint64 input, bytes proof, bytes data, bytes32 memo) {
    requireBooksInvariants();
    require balV(currentContract) == 0, "the property: the wrapper starts with no confidential balance";

    transferCall(e, variant, from, to, input, proof, data, memo);

    assert balV(currentContract) == 0, "the wrapper does not acquire a confidential balance";
}

/// A transfer-and-call to a contract can end with the whole amount refunded.
rule transferAndCallToContractCanBeRefunded(env e, uint8 variant, address from, address to,
        ERC7984ERC20WrapperHarness.externalEuint64 input, bytes proof, bytes data, bytes32 memo) {
    requireBooksInvariants();
    require isAndCallVariant(variant), "the property: the transfer-and-call variants";
    require from != 0 && to != 0 && from != to, "the property: a transfer between two distinct accounts (a transfer with the zero address as a party reverts)";
    require nativeCodesize[to] != 0, "the property: a recipient with code, so its hook runs";

    ERC7984ERC20WrapperHarness.euint64 net = transferCall(e, variant, from, to, input, proof, data, memo);

    satisfy fheVal(hA(net)) != 0 && fheVal(net) == 0;
}

/// A transfer-and-call to a contract can end with the receiver keeping the amount.
rule transferAndCallToContractCanBeAccepted(env e, uint8 variant, address from, address to,
        ERC7984ERC20WrapperHarness.externalEuint64 input, bytes proof, bytes data, bytes32 memo) {
    requireBooksInvariants();
    require isAndCallVariant(variant), "the property: the transfer-and-call variants";
    require from != 0 && to != 0 && from != to, "the property: a transfer between two distinct accounts (a transfer with the zero address as a party reverts)";
    require nativeCodesize[to] != 0, "the property: a recipient with code, so its hook runs";

    ERC7984ERC20WrapperHarness.euint64 net = transferCall(e, variant, from, to, input, proof, data, memo);

    satisfy fheVal(net) != 0;
}
