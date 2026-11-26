/*
 * ERC7984ERC20Wrapper: ACL permissions on encrypted values, authorization of the transfer entry points, and public
 * disclosure. The rules cover the permissions that stored handles keep, the permissions a transfer grants, the
 * checks on the caller of a transfer (operator authorization, permission on the amount handle), and who may make
 * an amount publicly decryptable.
 *
 * Model: setup/*.spec; the ACL is the ghosts `aclPersist`, `aclTransient`, `aclPublic` of setup/fhe.spec (F4):
 * permissions are only ever added, and `isAllowed` is a persistent or a transient permission. Grants made
 * by a call are compared by reading the ghosts before and after it, on a handle fixed by a rule parameter
 * (see setup/transfers.spec); "no new permission" means the permission was absent before and is absent
 * after. A rule that needs no permission of an account on a handle to start with states that as a
 * `require` on that handle (the equivalent of starting at a transaction boundary, for that handle).
 */
import "setup/invariants.spec";
import "setup/transfers.spec";

/// Every initialized stored balance handle stays persistently allowed to the wrapper (otherwise the balance freezes)
/// and to its holder (otherwise the holder can no longer decrypt it).
invariant storedBalanceHandlesRemainAclAccessible(address a)
    balHandle(a) != ZEROH() => (aclPersist[balHandle(a)][currentContract] && aclPersist[balHandle(a)][a]);

/// The stored total-supply handle stays persistently allowed to the wrapper.
invariant storedTotalSupplyHandleRemainsAclAccessible()
    tsHandle() != ZEROH() => aclPersist[tsHandle()][currentContract];

/// A transfer on behalf of `from` by another caller needs an unexpired operator authorization, valid up to and
/// including its expiry time.
rule transferFromRequiresHolderOrUnexpiredOperator(env e, uint8 variant, address from, address to,
        ERC7984ERC20WrapperHarness.externalEuint64 input, bytes proof, bytes data, bytes32 memo) {
    // the variants without `from` set `from == e.msg.sender` (setup/transfers.spec), so only the `from` variants remain
    require e.msg.sender != from, "the property: a caller other than `from`";
    require operatorUntil(from, e.msg.sender) < to_mathint(e.block.timestamp), "the property: the caller holds no unexpired operator authorization";

    bool reverted = transferReverts(e, variant, from, to, input, proof, data, memo);

    assert reverted, "a spend on behalf of `from` needs `from` itself or a live operator authorization";
}

/// A transfer of an existing encrypted amount fails unless the caller may use that handle. ERC7984 has no transfer
/// that takes a handle argument: an input with an empty proof is used as an existing handle (`FHE.fromExternal`). The
/// zero input is not an existing amount: it stands for an encryption of 0 and needs no permission.
rule handleAmountTransfersRequireCallerAcl(env e, uint8 variant, address from, address to,
        ERC7984ERC20WrapperHarness.externalEuint64 input, bytes proof, bytes data, bytes32 memo) {
    require proof.length == 0, "the property: an empty proof, so the input is an existing encrypted amount";
    require !isZeroHandle(input), "the property: an existing amount, not the uninitialized handle";
    require !cvlIsAllowed(input, e.msg.sender), "the property: the caller may not use the amount handle";

    bool reverted = transferReverts(e, variant, from, to, input, proof, data, memo);

    assert reverted, "the caller must be allowed on the amount handle";
}

function isZeroHandle(bytes32 h) returns bool {
    return h == ZEROH();
}

/// A transfer gives no third party, the calling operator included, any permission on the final balance handle of the
/// sender or of the recipient; gives neither party a new permission on the other's final balance handle; and gives a
/// third party no persistent permission on the amount it returns (the caller gets a transient one:
/// returnedHandleUsableByCaller). The two clauses between the parties exclude aliased handles: a handle is a
/// deterministic function of its operation and operands (F2), so a party's final balance handle can coincide with a
/// handle the call lets the other party use anyway, and then the permission is not on the other's balance in any
/// sense that matters. A party's own handles in a call are its final balance handle, the amount returned, in the
/// `*AndCall` variants the two legs `sent` and `refund` (`hA`, `hB` of the returned net amount) and the balance it
/// holds between the legs (`hA` of the sender's final handle, `hC` of the recipient's); the clauses leave out a final
/// handle that is one of the other party's. They also leave out the wrapper as a party: it holds a permission on
/// every balance handle (storedBalanceHandlesRemainAclAccessible). The third party is any account other than the two
/// parties, so the rule also covers the variants where the caller is the sender.
rule noCrossAccountBalanceAclGrants(env e, uint8 variant, address from, address to, address third,
        ERC7984ERC20WrapperHarness.externalEuint64 input, bytes proof, bytes data, bytes32 memo,
        bytes32 handleFrom, bytes32 handleTo, bytes32 handleMoved) {
    requireBooksInvariants();
    require from != 0 && to != 0 && from != to, "the property: a transfer between two distinct accounts (a transfer with the zero address as a party reverts)";
    require third != from && third != to && third != currentContract, "the property: a third party, neither of the two parties nor the wrapper";

    bool thirdOnFrom = cvlIsAllowed(handleFrom, third);
    bool thirdOnTo = cvlIsAllowed(handleTo, third);
    bool toOnFrom = aclPersist[handleFrom][to];
    bool fromOnTo = aclPersist[handleTo][from];
    bool thirdPersistsOnMoved = aclPersist[handleMoved][third];

    ERC7984ERC20WrapperHarness.euint64 moved = transferCall(e, variant, from, to, input, proof, data, memo);

    require handleFrom == balHandle(from) && handleTo == balHandle(to) && handleMoved == moved,
        "the handle parameters name the final balance handles and the returned amount, so the rule covers every handle (setup/transfers.spec)";

    // the final balance handle of one party is also one of the other party's own handles in this call
    bool recipientHandleIsSenders = handleTo == handleFrom || handleTo == handleMoved
        || handleTo == hA(handleMoved) || handleTo == hB(handleMoved) || handleTo == hA(handleFrom);
    bool senderHandleIsRecipients = handleFrom == handleTo || handleFrom == handleMoved
        || handleFrom == hA(handleMoved) || handleFrom == hB(handleMoved) || handleFrom == hC(handleTo);

    assert !thirdOnFrom => !cvlIsAllowed(handleFrom, third), "no third party gains access to the sender's balance";
    assert !thirdOnTo => !cvlIsAllowed(handleTo, third), "no third party gains access to the recipient's balance";
    assert (to != currentContract && !senderHandleIsRecipients && !toOnFrom) => !aclPersist[handleFrom][to],
        "the recipient gains no permission on the sender's balance (unless the handle is one of the recipient's own, or the recipient is the wrapper)";
    assert (from != currentContract && !recipientHandleIsSenders && !fromOnTo) => !aclPersist[handleTo][from],
        "the sender gains no permission on the recipient's balance (unless the handle is one of the sender's own, or the sender is the wrapper)";
    assert !thirdPersistsOnMoved => !aclPersist[handleMoved][third], "no third party gets a persistent permission on the amount moved";
}

/// Requesting the public disclosure of an encrypted amount fails unless the caller may use it. This holds whether or
/// not a transient permission is meant to be enough (see the next rule).
rule disclosureRequiresCallerAllowance(env e, ERC7984ERC20WrapperHarness.euint64 h) {
    require !cvlIsAllowed(h, e.msg.sender), "the property: the caller may not use the handle";

    requestDiscloseEncryptedAmount@withrevert(e, h);

    assert lastReverted, "only a party that may use a handle can make it publicly decryptable";
}

/// An operator whose only right on the amount a transfer returned is the transient one that
/// `confidentialTransferFrom` hands it cannot make that amount publicly decryptable, which is irreversible. The rule
/// states that a persistent permission is required to request disclosure, not a transient one.
rule transientAllowanceCannotBeEscalatedToPublicDisclosure(env e, address from, address to,
        ERC7984ERC20WrapperHarness.externalEuint64 input, bytes proof, bytes32 handleMoved) {
    address operator = e.msg.sender;
    require operator != from && operator != to && operator != currentContract, "the property: an operator that is neither party nor the wrapper";
    require from != 0 && to != 0, "the property: a transfer between two accounts (a transfer with the zero address as a party reverts)";
    // the operator has no permission of any kind on the amount before the call: what it holds afterwards is
    // granted by the call
    require !cvlIsAllowed(handleMoved, operator), "the property: the operator holds no permission on the amount before the call";

    ERC7984ERC20WrapperHarness.euint64 moved = confidentialTransferFrom(e, from, to, input, proof);

    require handleMoved == moved, "the handle parameter names the returned amount, so the rule covers every handle (setup/transfers.spec)";
    // the call granted the operator no persistent permission on it
    require !aclPersist[handleMoved][operator], "the property: the operator's only right on the amount is the transient one the call grants";

    requestDiscloseEncryptedAmount@withrevert(e, moved);

    assert lastReverted, "a transient permission must not let its holder publish the amount forever";
}

/// Every transfer entry point leaves its caller allowed on the handle it returns: the sender persistently, an
/// operator transiently.
rule returnedHandleUsableByCaller(env e, uint8 variant, address from, address to,
        ERC7984ERC20WrapperHarness.externalEuint64 input, bytes proof, bytes data, bytes32 memo) {
    ERC7984ERC20WrapperHarness.euint64 moved = transferCall(e, variant, from, to, input, proof, data, memo);

    assert cvlIsAllowed(moved, e.msg.sender), "the caller may use the amount it is told was moved";
}
