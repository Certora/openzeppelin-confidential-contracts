/*
 * Model of the underlying ERC-20 token for the ERC7984ERC20Wrapper specs.
 *
 * The underlying token lives at an address held in an immutable of the wrapper, so the Prover has no
 * code for it. Its balances are ghosts (`uBal[token][account]`). The wrapper moves tokens only through
 * OpenZeppelin SafeERC20, which is summarized here; `balanceOf` is summarized for
 * `inferredTotalSupply`.
 *
 * Assumptions:
 *  U1. A transfer moves exactly the nominal amount (no fee on transfer, no rebasing), touches no
 *      other balance, and makes no callback into the wrapper.
 *  U2. A transfer may be refused (ghost `uTokenRejects`, which SafeERC20 turns into a revert) and
 *      reverts on an insufficient balance or an overflowing credit, as a standard ERC-20 does.
 *      Allowances are not modelled: a missing approval is one of the reasons for a refusal.
 *  U3. `decimals()` is not modelled here. The wrapper calls it only in its constructor, where the Prover
 *      cannot resolve the call and havocs its answer (params.spec).
 *  U4. Every outgoing transfer of the wrapper is logged (`outCount`, `lastOutTo`, `lastOutAmount`,
 *      `lastOutToken`) so rules can state where the underlying went.
 *  U5. Any `approve(address,uint256)` call made by the wrapper is counted in `approveCalls`.
 *  U6. The underlying token is a deployed contract other than the wrapper: not address 0 and not the wrapper
 *      itself. The constructor does not check its `underlying_` argument, so this cannot be an invariant. In
 *      the real code such a wrapper moves nothing: SafeERC20 reverts on an address without code, and the
 *      wrapper has no ERC-20 functions, so every wrap, every unwrap finalization and `inferredTotalSupply`
 *      reverts. The ghost balances here would let those calls succeed.
 */

ghost mapping(address => mapping(address => uint256)) uBal;
ghost bool uTokenRejects;

ghost mathint outCount;
ghost address lastOutToken;
ghost address lastOutTo;
ghost mathint lastOutAmount;

ghost mathint approveCalls;

methods {
    function SafeERC20.safeTransfer(address token, address to, uint256 value) internal
        => cvlSafeTransfer(token, to, value);
    function SafeERC20.safeTransferFrom(address token, address from, address to, uint256 value) internal
        => cvlSafeTransferFrom(token, from, to, value);

    function _.balanceOf(address account) external => cvlBalanceOf(calledContract, account) expect uint256;
    function _.approve(address spender, uint256 amount) external => cvlApprove(calledContract, spender, amount) expect bool;
}

function cvlMove(address token, address from, address to, uint256 amount) {
    if (uTokenRejects) {
        revert("U2: the token refused the transfer");
    }
    if (uBal[token][from] < amount) {
        revert("U2: insufficient balance");
    }
    if (from != to) {
        if (to_mathint(uBal[token][to]) + amount > max_uint256) {
            revert("U2: balance overflow");
        }
        uBal[token][from] = assert_uint256(uBal[token][from] - amount);
        uBal[token][to] = require_uint256(uBal[token][to] + amount);
    }
}

function cvlSafeTransfer(address token, address to, uint256 value) {
    cvlMove(token, currentContract, to, value);
    outCount = outCount + 1;
    lastOutToken = token;
    lastOutTo = to;
    lastOutAmount = value;
}

function cvlSafeTransferFrom(address token, address from, address to, uint256 value) {
    cvlMove(token, from, to, value);
    if (from == currentContract) {
        outCount = outCount + 1;
        lastOutToken = token;
        lastOutTo = to;
        lastOutAmount = value;
    }
}

function cvlBalanceOf(address token, address account) returns uint256 {
    return uBal[token][account];
}

function cvlApprove(address token, address spender, uint256 amount) returns bool {
    approveCalls = approveCalls + 1;
    bool ok;
    return ok;
}

/// The wrapper's holding of its underlying token (an immutable, so read through its getter).
function heldByWrapper() returns mathint {
    return uBal[underlying()][currentContract];
}
