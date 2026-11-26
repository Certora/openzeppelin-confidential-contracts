/*
 * ERC7984ERC20Wrapper: wrapping, by `wrap` and by the ERC-1363 callback `onTransferReceived`: the amounts taken,
 * credited and refunded, the recipient, the revert conditions, and the cap of the supply at 2^64 - 1.
 *
 * Model: setup/*.spec. The underlying token is ghost-modelled (U1-U6).
 */
import "setup/invariants.spec";

/// ERC-1363 acceptance value, IERC1363Receiver.onTransferReceived.selector.
definition ERC1363_RECEIVED() returns bytes4 = to_bytes4(0x88a7ca5c);

/// Wrapping `x` takes exactly `x - x mod rate` from the depositor, credits the recipient with exactly `floor(x /
/// rate)`, and changes no other balance.
rule wrapTakesRoundedAmountAndCreditsQuotient(env e, address to, uint256 x, address other) {
    requireBooksInvariants();
    require other != to, "the frame condition is about every account other than the recipient";
    require e.msg.sender != currentContract,
        "the wrapper never calls its own wrap; as its own depositor the token model moves nothing";

    address token = underlying();
    mathint r = rate();
    address depositor = e.msg.sender;
    mathint depositorHeld = uBal[token][depositor];
    mathint wrapperHeld = uBal[token][currentContract];
    mathint balTo = balV(to);
    mathint balOther = balV(other);
    mathint supply = tsV();

    ERC7984ERC20WrapperHarness.euint64 minted = wrap(e, to, x);

    mathint taken = x - x % r;
    mathint credited = x / r;
    assert to_mathint(uBal[token][depositor]) == depositorHeld - taken;
    assert to_mathint(uBal[token][currentContract]) == wrapperHeld + taken;
    assert fheVal(minted) == credited, "the returned amount is the exact quotient";
    assert balV(to) == balTo + credited;
    assert tsV() == supply + credited;
    assert balV(other) == balOther;
}

/// A wrap to the zero address is rejected.
rule wrapToZeroAddressReverts(env e, uint256 x) {
    wrap@withrevert(e, 0, x);
    assert lastReverted;
}

/// A successful wrap never makes `underlying_held / rate` exceed the 64-bit maximum.
rule wrapRespectsSupplyCap(env e, address to, uint256 x) {
    wrap(e, to, x);

    assert heldByWrapper() / rate() <= MAX64();
}

/// Only the underlying token can trigger a callback wrap.
rule callbackWrapOnlyFromUnderlying(env e, address operator, address from, uint256 amount, bytes data) {
    require e.msg.sender != underlying(), "the revert condition: the caller is not the underlying token";
    onTransferReceived@withrevert(e, operator, from, amount, data);
    assert lastReverted;
}

/// With empty callback data the sender is credited `floor(amount / rate)`, the remainder `amount mod rate` goes back
/// to the sender, and the callback is accepted.
rule callbackWrapWithEmptyDataCreditsSender(env e, address operator, address from, uint256 amount, bytes data, address other) {
    requireBooksInvariants();
    require surplus() >= to_mathint(amount), "rule hypothesis: the token delivered `amount` before calling back, as ERC-1363 does";
    require data.length == 0, "the property is about empty callback data";
    require from != currentContract, "the wrapper never calls transferAndCall on its own underlying, so it is not the sender of an ERC-1363 callback";
    require other != from, "the frame condition is about every account other than the credited sender";

    address token = underlying();
    mathint r = rate();
    mathint fromHeld = uBal[token][from];
    mathint wrapperHeld = uBal[token][currentContract];
    mathint balFrom = balV(from);
    mathint balOther = balV(other);
    mathint supply = tsV();
    require outCount == 0, "the log of outgoing underlying transfers (U4) starts empty, so it shows what this call alone sent";

    bytes4 ret = onTransferReceived(e, operator, from, amount, data);

    assert ret == ERC1363_RECEIVED();
    assert balV(from) == balFrom + amount / r;
    assert balV(other) == balOther;
    assert tsV() == supply + amount / r;
    assert to_mathint(uBal[token][from]) == fromHeld + amount % r;
    assert to_mathint(uBal[token][currentContract]) == wrapperHeld - amount % r;
    assert amount % r == 0 <=> outCount == 0, "a refund is made exactly when there is a remainder";
}

/// With callback data that is exactly a 20-byte address, that address is credited `floor(amount / rate)` and the
/// remainder goes back to the sender.
rule callbackWrapWithAddressDataCreditsThatAddress(env e, address operator, address from, uint256 amount, address recipient, address other) {
    requireBooksInvariants();
    require surplus() >= to_mathint(amount), "rule hypothesis: the token delivered `amount` before calling back, as ERC-1363 does";
    require from != currentContract, "the wrapper never calls transferAndCall on its own underlying, so it is not the sender of an ERC-1363 callback";
    require other != recipient, "the frame condition is about every account other than the recipient";

    bytes data = helper.encodeRecipient(recipient);
    address token = underlying();
    mathint r = rate();
    mathint fromHeld = uBal[token][from];
    mathint balRecipient = balV(recipient);
    mathint balOther = balV(other);
    mathint supply = tsV();

    onTransferReceived(e, operator, from, amount, data);

    assert balV(recipient) == balRecipient + amount / r;
    assert balV(other) == balOther;
    assert tsV() == supply + amount / r;
    assert to_mathint(uBal[token][from]) == fromHeld + amount % r;
}

/// Callback data that is neither empty nor exactly 20 bytes is rejected.
rule callbackWrapWithOtherDataReverts(env e, address operator, address from, uint256 amount, bytes data) {
    require data.length != 0 && data.length != 20, "the revert condition: the data is neither empty nor a 20-byte address";
    onTransferReceived@withrevert(e, operator, from, amount, data);
    assert lastReverted;
}

/// A callback wrap naming the zero address as recipient is rejected.
rule callbackWrapToZeroRecipientReverts(env e, address operator, address from, uint256 amount) {
    bytes data = helper.encodeRecipient(0);
    onTransferReceived@withrevert(e, operator, from, amount, data);
    assert lastReverted;
}

/// A successful callback wrap never makes `underlying_held / rate` exceed the 64-bit maximum.
rule callbackWrapRespectsSupplyCap(env e, address operator, address from, uint256 amount, bytes data) {
    onTransferReceived(e, operator, from, amount, data);

    assert heldByWrapper() / rate() <= MAX64();
}
