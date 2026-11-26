/*
 * Plaintext view of the wrapper's books: balances, supply and pending unwrap requests.
 *
 * Mirrors are kept by storage hooks on the fields of ERC7984 and ERC7984ERC20Wrapper. Values are the
 * plaintexts `fheVal(handle)` of fhe.spec.
 *
 *  - `sumBalances`  : sum over all accounts of the plaintext balance.
 *  - `sumPending`   : sum over all pending unwrap requests of the burned plaintext amount. A request id
 *                     is the handle of the burned amount, so a pending request `id` holds `fheVal(id)`.
 *
 * L1 (the only bare assumption): a single term of a sum of non-negative terms never exceeds the sum.
 *    The Sload hooks import this fact, which CVL's hook-maintained sums cannot express. No reachable
 *    state violates it.
 */

ghost mapping(address => bytes32) balMirror {
    init_state axiom forall address a. balMirror[a] == to_bytes32(0);
}
ghost bytes32 tsMirror {
    init_state axiom tsMirror == to_bytes32(0);
}
ghost mathint sumBalances {
    init_state axiom sumBalances == 0;
}
ghost mathint sumPending {
    init_state axiom sumPending == 0;
}

/// Balance-write log: the account whose confidential balance was written last, and how many writes there were (reset
/// with `resetBalanceLog`). It names the beneficiary of an ERC-1363 wrap, who sits in the `data` payload. It lives
/// here because the Prover allows one hook per storage pattern.
persistent ghost address lastBalanceWritten;
persistent ghost mathint balanceWriteCount;

hook Sstore currentContract._balances[KEY address a]
        ERC7984ERC20WrapperHarness.euint64 newH (ERC7984ERC20WrapperHarness.euint64 oldH) {
    balMirror[a] = newH;
    sumBalances = sumBalances + fheVal(newH) - fheVal(oldH);
    lastBalanceWritten = a;
    balanceWriteCount = balanceWriteCount + 1;
}

function resetBalanceLog() {
    lastBalanceWritten = 0;
    balanceWriteCount = 0;
}

hook Sload ERC7984ERC20WrapperHarness.euint64 h currentContract._balances[KEY address a] {
    require balMirror[a] == h, "the mirror ghost holds the handle stored for the account";
    require fheVal(h) <= sumBalances, "L1";
}

hook Sstore currentContract._totalSupply ERC7984ERC20WrapperHarness.euint64 newH {
    tsMirror = newH;
}

hook Sload ERC7984ERC20WrapperHarness.euint64 h currentContract._totalSupply {
    require tsMirror == h, "the mirror ghost holds the stored total-supply handle";
}

/// A request is pending while its recipient is non-zero (`finalizeUnwrap` treats a zero recipient as no request).
hook Sstore currentContract._unwrapRequests[KEY bytes32 id].recipient address newR (address oldR) {
    sumPending = sumPending + (newR != 0 ? fheVal(id) : 0) - (oldR != 0 ? fheVal(id) : 0);
}

hook Sload address r currentContract._unwrapRequests[KEY bytes32 id].recipient {
    require r != 0 => fheVal(id) <= sumPending, "L1";
}

function balV(address a) returns mathint {
    return fheVal(balMirror[a]);
}

function tsV() returns mathint {
    return fheVal(tsMirror);
}

function balHandle(address a) returns bytes32 {
    return currentContract._balances[a];
}

function tsHandle() returns bytes32 {
    return currentContract._totalSupply;
}

function requesterOf(bytes32 id) returns address {
    return currentContract._unwrapRequests[id].recipient;
}

function requestMetadata(bytes32 id) returns bytes12 {
    return currentContract._unwrapRequests[id].metadata;
}

function operatorUntil(address holder, address spender) returns mathint {
    return currentContract._operators[holder][spender];
}
