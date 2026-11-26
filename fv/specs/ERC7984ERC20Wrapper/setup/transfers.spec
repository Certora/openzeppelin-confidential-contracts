/*
 * The eight confidential-transfer entry points of ERC7984 behind one dispatcher, for the specs that state one
 * property for every variant:
 *
 *   0 confidentialTransfer(to, input, proof)                 1 confidentialTransfer(to, input, proof, memo)
 *   2 confidentialTransferFrom(from, to, input, proof)       3 confidentialTransferFrom(from, to, input, proof, memo)
 *   4 confidentialTransferAndCall(to, input, proof, data)    5 confidentialTransferAndCall(to, input, proof, data, memo)
 *   6 confidentialTransferFromAndCall(from, to, input, proof, data)
 *   7 confidentialTransferFromAndCall(from, to, input, proof, data, memo)
 *
 * The forms without a memo pass `bytes32(0)` to the memo forms. The variants without `from` act on the caller's
 * own tokens, so `from` is the caller there. The dispatcher puts no condition on the input proof. With a
 * non-empty proof `FHE.fromExternal` verifies the input and yields `verifiedHandle(input)`; with an empty proof it
 * re-uses the input as an existing handle, which the caller must be allowed to use (a zero input gives the trivial
 * encryption of 0). A rule that names the amount through `transferAmountHandle` must say
 * `require proof.length > 0`.
 *
 * `transferCall` runs a variant and keeps only the non-reverting executions. `transferCallWithRevert`
 * (the `@withrevert` form) also reports whether the call reverted; the handle it returns is meaningful
 * only when it did not. `transferReverts` is the same call reduced to the revert flag.
 *
 * ACL comparisons around a call: a rule that asks "what did this call grant" picks the handle and the
 * account as rule parameters, reads the ACL ghosts (`aclPersist`, `aclTransient`, `aclPublic`) before the
 * call, then pins the parameter to the handle of interest after it (`require h == balHandle(a)`). That
 * is a statement about every handle, without a quantified assumption on the ACL.
 */
import "base.spec";

definition isValidVariant(uint8 v) returns bool = v <= 7;
definition isFromVariant(uint8 v) returns bool = v == 2 || v == 3 || v == 6 || v == 7;
definition isAndCallVariant(uint8 v) returns bool = v >= 4 && v <= 7;
definition isMemoVariant(uint8 v) returns bool = v == 1 || v == 3 || v == 5 || v == 7;

/// Handle of the amount a transfer asks for, for a non-empty input proof (the caller requires `proof.length > 0`).
function transferAmountHandle(ERC7984ERC20WrapperHarness.externalEuint64 input) returns bytes32 {
    return verifiedHandle(input);
}

/// The shape every call of the dispatcher assumes: a valid variant, and `from` the caller for the variants without
/// `from`.
function requireTransferShape(env e, uint8 variant, address from) {
    require isValidVariant(variant), "the dispatcher has the eight variants 0 to 7";
    if (!isFromVariant(variant)) {
        require from == e.msg.sender, "the variants without `from` act on the caller's own tokens";
    }
}

/// Runs the selected transfer entry point and returns the handle it returns (the amount transferred; for the
/// `*AndCall` variants the net amount `sent - refund`).
function transferCall(env e, uint8 variant, address from, address to,
        ERC7984ERC20WrapperHarness.externalEuint64 input, bytes proof, bytes data, bytes32 memo)
        returns ERC7984ERC20WrapperHarness.euint64 {
    requireTransferShape(e, variant, from);
    ERC7984ERC20WrapperHarness.euint64 transferred;
    if (variant == 0) {
        transferred = confidentialTransfer(e, to, input, proof);
    } else if (variant == 1) {
        transferred = confidentialTransfer(e, to, input, proof, memo);
    } else if (variant == 2) {
        transferred = confidentialTransferFrom(e, from, to, input, proof);
    } else if (variant == 3) {
        transferred = confidentialTransferFrom(e, from, to, input, proof, memo);
    } else if (variant == 4) {
        transferred = confidentialTransferAndCall(e, to, input, proof, data);
    } else if (variant == 5) {
        transferred = confidentialTransferAndCall(e, to, input, proof, data, memo);
    } else if (variant == 6) {
        transferred = confidentialTransferFromAndCall(e, from, to, input, proof, data);
    } else {
        transferred = confidentialTransferFromAndCall(e, from, to, input, proof, data, memo);
    }
    return transferred;
}

/// The `@withrevert` form of `transferCall`: whether the call reverted, and the handle it returned.
function transferCallWithRevert(env e, uint8 variant, address from, address to,
        ERC7984ERC20WrapperHarness.externalEuint64 input, bytes proof, bytes data, bytes32 memo)
        returns (bool, ERC7984ERC20WrapperHarness.euint64) {
    requireTransferShape(e, variant, from);
    ERC7984ERC20WrapperHarness.euint64 transferred;
    if (variant == 0) {
        transferred = confidentialTransfer@withrevert(e, to, input, proof);
    } else if (variant == 1) {
        transferred = confidentialTransfer@withrevert(e, to, input, proof, memo);
    } else if (variant == 2) {
        transferred = confidentialTransferFrom@withrevert(e, from, to, input, proof);
    } else if (variant == 3) {
        transferred = confidentialTransferFrom@withrevert(e, from, to, input, proof, memo);
    } else if (variant == 4) {
        transferred = confidentialTransferAndCall@withrevert(e, to, input, proof, data);
    } else if (variant == 5) {
        transferred = confidentialTransferAndCall@withrevert(e, to, input, proof, data, memo);
    } else if (variant == 6) {
        transferred = confidentialTransferFromAndCall@withrevert(e, from, to, input, proof, data);
    } else {
        transferred = confidentialTransferFromAndCall@withrevert(e, from, to, input, proof, data, memo);
    }
    return (lastReverted, transferred);
}

/// Whether the selected transfer entry point reverts.
function transferReverts(env e, uint8 variant, address from, address to,
        ERC7984ERC20WrapperHarness.externalEuint64 input, bytes proof, bytes data, bytes32 memo) returns bool {
    bool reverted;
    ERC7984ERC20WrapperHarness.euint64 transferred;
    reverted, transferred = transferCallWithRevert(e, variant, from, to, input, proof, data, memo);
    return reverted;
}
