/*
 * Model of the FHEVM coprocessor, ACL and KMS verifier for the ERC7984ERC20Wrapper specs.
 *
 * Every FHE operation is an external call from fhevm's `Impl` library (@fhevm/solidity 0.13.3) to the
 * coprocessor or the ACL, at addresses the Prover cannot resolve, so the calls are summarized at the `Impl`
 * boundary.
 *
 * Each summary attaches the plaintext and provenance of the handle it returns. Quantified axioms over
 * operand handles would be instantiated for every combination of handles in a rule; on the
 * transfer-and-call paths that ran the Prover out of resources.
 *
 * Assumptions (everything proved on top of this file excludes their negation):
 *  F1. Homomorphic arithmetic is exact modulo 2^64; comparisons and select are exact.
 *  F2. A result handle is a deterministic function of the operation and its operand handles, and
 *      distinct computations give distinct handles (keccak collision freedom). Provenance is acyclic:
 *      a result ranks above each of its operands (`hRank`), so no handle is, directly or through
 *      other operations, its own operand. A free pre-state could otherwise hold handles that equal
 *      results the transaction computes later from them.
 *  F3. The plaintext behind a handle never changes (`fheVal` is fixed for the whole rule).
 *  F4. The coprocessor's own ACL checks on operands are not modelled: every operation succeeds.
 *  F5. KMS signature verification either accepts or rejects (ghost `kmsAccepts`). Whether the
 *      accepted cleartext equals the decrypted handle is the KMS's guarantee; rules that need it
 *      state it explicitly (`fheVal(handle) == cleartext`).
 *
 * The ACL's user-decryption delegations are not modelled: neither ERC7984 nor ERC7984ERC20Wrapper delegates.
 */

definition MAX64() returns mathint = 18446744073709551615;
definition ZEROH() returns bytes32 = to_bytes32(0);

definition OP_TRIV()   returns mathint = 0;
definition OP_ADD()    returns mathint = 1;
definition OP_SUB()    returns mathint = 2;
definition OP_GE()     returns mathint = 3;
definition OP_LE()     returns mathint = 4;
definition OP_EQ()     returns mathint = 5;
definition OP_NE()     returns mathint = 6;
definition OP_SEL()    returns mathint = 7;
definition OP_VERIFY() returns mathint = 8;
definition OP_MIN()    returns mathint = 9;
definition OP_MAX()    returns mathint = 10;

/// Plaintext behind a handle. The uninitialized handle denotes 0, as in FHE.sol.
ghost fheVal(bytes32) returns mathint {
    axiom fheVal(to_bytes32(0)) == 0;
    axiom forall bytes32 h. fheVal(h) >= 0 && fheVal(h) <= MAX64();
}

/// Result handle of an operation on operand handles (F2). Its plaintext (F1) is attached by the summary that produces
/// it.
ghost fheOpH(mathint, bytes32, bytes32, bytes32) returns bytes32;

/// Handle of a trivially encrypted cleartext; its plaintext is attached by `trivialHandle`.
ghost fheTrivH(mathint) returns bytes32;

/// Provenance of a handle (which operation produced it, from which operands). Materialised by the summaries below;
/// encodes F2 and lets rules reach intermediate handles.
ghost hOp(bytes32) returns mathint {
    axiom hOp(to_bytes32(0)) == -1;
}
ghost hA(bytes32) returns bytes32;
ghost hB(bytes32) returns bytes32;
ghost hC(bytes32) returns bytes32;
/// Position of a handle in the order of computation (F2): a result ranks above its operands.
ghost hRank(bytes32) returns mathint;

/* ------------------------------------------------------------------ ACL state */

ghost mapping(bytes32 => mapping(address => bool)) aclPersist;
ghost mapping(bytes32 => mapping(address => bool)) aclTransient;
/// Publicly decryptable (irreversible).
ghost mapping(bytes32 => bool) aclPublic;

/* ------------------------------------------------------------------ KMS state */

/// KMS answer for a public-decryption proof of a handle (F5).
ghost mapping(bytes32 => bool) kmsAccepts;
/// Handle passed to the last successful KMS check in the current transaction, and how many checks ran.
ghost bytes32 kmsCheckedHandle;
ghost mathint kmsChecks;

/* ------------------------------------------------------------------ summaries */

methods {
    function Impl.add(bytes32 l, bytes32 r, bool s) internal returns (bytes32) => cvlFheBin(OP_ADD(), l, r, s);
    function Impl.sub(bytes32 l, bytes32 r, bool s) internal returns (bytes32) => cvlFheBin(OP_SUB(), l, r, s);
    function Impl.ge(bytes32 l, bytes32 r, bool s)  internal returns (bytes32) => cvlFheBin(OP_GE(), l, r, s);
    function Impl.le(bytes32 l, bytes32 r, bool s)  internal returns (bytes32) => cvlFheBin(OP_LE(), l, r, s);
    function Impl.eq(bytes32 l, bytes32 r, bool s)  internal returns (bytes32) => cvlFheBin(OP_EQ(), l, r, s);
    function Impl.ne(bytes32 l, bytes32 r, bool s)  internal returns (bytes32) => cvlFheBin(OP_NE(), l, r, s);
    function Impl.min(bytes32 l, bytes32 r, bool s) internal returns (bytes32) => cvlFheBin(OP_MIN(), l, r, s);
    function Impl.max(bytes32 l, bytes32 r, bool s) internal returns (bytes32) => cvlFheBin(OP_MAX(), l, r, s);
    function Impl.select(bytes32 c, bytes32 a, bytes32 b) internal returns (bytes32) => cvlFheSelect(c, a, b);

    function Impl.trivialEncrypt(uint256 v, ERC7984ERC20WrapperHarness.FheType t) internal returns (bytes32) => cvlTrivial(v);
    function Impl.verify(bytes32 h, bytes memory p, ERC7984ERC20WrapperHarness.FheType t) internal returns (bytes32)
        with (env e) => cvlVerify(e, h);

    function Impl.allow(bytes32 h, address a)          internal => cvlAllow(h, a);
    function Impl.allowTransient(bytes32 h, address a) internal => cvlAllowTransient(h, a);
    function Impl.isAllowed(bytes32 h, address a)      internal returns (bool) => cvlIsAllowed(h, a);
    function Impl.persistAllowed(bytes32 h, address a) internal returns (bool) => cvlPersistAllowed(h, a);
    function Impl.makePubliclyDecryptable(bytes32 h)   internal => cvlMakePublic(h);
    function Impl.isPubliclyDecryptable(bytes32 h)     internal returns (bool) => cvlIsPublic(h);

    function FHE.checkSignatures(bytes32[] memory h, bytes memory c, bytes memory p) internal => cvlCheckSignatures(h);
}

/// Plaintext of the binary operation `op` on operand plaintexts `a` and `b` (F1).
function fheBinVal(mathint op, mathint a, mathint b) returns mathint {
    if (op == OP_ADD()) {
        return a + b <= MAX64() ? a + b : a + b - (MAX64() + 1);
    } else if (op == OP_SUB()) {
        return a >= b ? a - b : a - b + (MAX64() + 1);
    } else if (op == OP_GE()) {
        return a >= b ? 1 : 0;
    } else if (op == OP_LE()) {
        return a <= b ? 1 : 0;
    } else if (op == OP_EQ()) {
        return a == b ? 1 : 0;
    } else if (op == OP_NE()) {
        return a != b ? 1 : 0;
    } else if (op == OP_MIN()) {
        return a <= b ? a : b;
    } else {
        require op == OP_MAX(), "only the binary operations above are summarized";
        return a >= b ? a : b;
    }
}

/// Handle of the trivial encryption of `v`, with its plaintext.
function trivialHandle(uint256 v) returns bytes32 {
    bytes32 res = fheTrivH(v);
    require res != ZEROH(), "F2: a result is never the uninitialized handle";
    require to_mathint(v) <= MAX64() => fheVal(res) == to_mathint(v), "F1";
    return res;
}

function cvlFheBin(mathint op, bytes32 l, bytes32 r, bool scalar) returns bytes32 {
    bytes32 rh;
    if (scalar) {
        rh = trivialHandle(require_uint256(r));
    } else {
        rh = r;
    }
    bytes32 res = fheOpH(op, l, rh, ZEROH());
    require res != ZEROH(), "F2: a result is never the uninitialized handle";
    require fheVal(res) == fheBinVal(op, fheVal(l), fheVal(rh)), "F1";
    require hOp(res) == op && hA(res) == l && hB(res) == rh && hC(res) == ZEROH(), "F2: handle provenance";
    require hRank(res) > hRank(l) && hRank(res) > hRank(rh), "F2: a result comes after its operands";
    aclTransient[res][currentContract] = true;
    return res;
}

function cvlFheSelect(bytes32 c, bytes32 a, bytes32 b) returns bytes32 {
    bytes32 res = fheOpH(OP_SEL(), c, a, b);
    require res != ZEROH(), "F2: a result is never the uninitialized handle";
    require fheVal(res) == (fheVal(c) != 0 ? fheVal(a) : fheVal(b)), "F1";
    require hOp(res) == OP_SEL() && hA(res) == c && hB(res) == a && hC(res) == b, "F2: handle provenance";
    require hRank(res) > hRank(c) && hRank(res) > hRank(a) && hRank(res) > hRank(b), "F2: a result comes after its operands";
    aclTransient[res][currentContract] = true;
    return res;
}

function cvlTrivial(uint256 v) returns bytes32 {
    bytes32 res = trivialHandle(v);
    require hOp(res) == OP_TRIV() && hA(res) == to_bytes32(v), "F2: handle provenance";
    aclTransient[res][currentContract] = true;
    return res;
}

function cvlVerify(env e, bytes32 inputHandle) returns bytes32 {
    bytes32 res = fheOpH(OP_VERIFY(), inputHandle, ZEROH(), ZEROH());
    require res != ZEROH(), "F2: a result is never the uninitialized handle";
    require hOp(res) == OP_VERIFY() && hA(res) == inputHandle, "F2: handle provenance";
    require hRank(res) > hRank(inputHandle), "F2: a result comes after its operands";
    aclTransient[res][currentContract] = true;
    aclTransient[res][e.msg.sender] = true;
    return res;
}

function cvlAllow(bytes32 h, address a) {
    aclPersist[h][a] = true;
}

function cvlAllowTransient(bytes32 h, address a) {
    aclTransient[h][a] = true;
}

function cvlIsAllowed(bytes32 h, address a) returns bool {
    return aclPersist[h][a] || aclTransient[h][a];
}

function cvlPersistAllowed(bytes32 h, address a) returns bool {
    return aclPersist[h][a];
}

function cvlMakePublic(bytes32 h) {
    aclPublic[h] = true;
}

function cvlIsPublic(bytes32 h) returns bool {
    return aclPublic[h];
}

function cvlCheckSignatures(bytes32[] h) {
    require h.length == 1, "the wrapper always verifies a single handle";
    if (!kmsAccepts[h[0]]) {
        revert("KMS rejects the decryption proof");
    }
    kmsCheckedHandle = h[0];
    kmsChecks = kmsChecks + 1;
}

/// Handle produced by `FHE.fromExternal` for an input with a non-empty proof.
function verifiedHandle(bytes32 ext) returns bytes32 {
    return fheOpH(OP_VERIFY(), ext, ZEROH(), ZEROH());
}
