/*
 * Common setup for the ERC7984ERC20Wrapper specs: the encrypted-value model, the underlying token
 * model, the plaintext ledger, the receiver-callback model and shared definitions.
 *
 * The contract under verification is fv/harnesses/ERC7984ERC20WrapperHarness.sol: ERC7984ERC20Wrapper with
 * ZamaEthereumConfig and no entry point of its own.
 */
import "fhe.spec";
import "underlying.spec";
import "ledger.spec";

using WrapperSpecHelper as helper;

methods {
    function underlying() external returns (address) envfree;
    function rate() external returns (uint256) envfree;
    function decimals() external returns (uint8) envfree;
    function unwrapRequester(bytes32) external returns (address) envfree;
    function inferredTotalSupply() external returns (uint256) envfree;
    function maxTotalSupply() external returns (uint256) envfree;

    function helper.encodeRecipient(address) external returns (bytes) envfree;
    function helper.erc7984InterfaceId() external returns (bytes4) envfree;
    function helper.erc7984ERC20WrapperInterfaceId() external returns (bytes4) envfree;
    function helper.erc1363ReceiverInterfaceId() external returns (bytes4) envfree;
    function helper.erc165InterfaceId() external returns (bytes4) envfree;

    /*
     * IERC7984Receiver callback of the *AndCall transfers. R1: the receiver either reverts or returns
     * an arbitrary acceptance handle, and changes no state (no reentrancy, no spending of what it just
     * received). The documented best-effort-refund case is therefore outside this model. The answer
     * is a fixed function of receiver and amount, so two runs from the same state agree.
     */
    function _.onConfidentialTransferReceived(address operator, address from, ERC7984ERC20WrapperHarness.euint64 amount, bytes data)
        external => cvlReceiver(calledContract, amount) expect ERC7984ERC20WrapperHarness.ebool;
}

ghost receiverFails(address, bytes32) returns bool;
ghost receiverAnswer(address, bytes32) returns ERC7984ERC20WrapperHarness.ebool;

function cvlReceiver(address receiver, bytes32 amount) returns ERC7984ERC20WrapperHarness.ebool {
    if (receiverFails(receiver, amount)) {
        revert("R1: receiver callback failed");
    }
    return receiverAnswer(receiver, amount);
}

/// Selectors of the entry points that move confidential tokens or underlying tokens.
definition isWrapEntry(method f) returns bool =
    f.selector == sig:wrap(address, uint256).selector
    || f.selector == sig:onTransferReceived(address, address, uint256, bytes).selector;

definition isUnwrapEntry(method f) returns bool =
    f.selector == sig:unwrap(address, address, ERC7984ERC20WrapperHarness.euint64).selector
    || f.selector == sig:unwrap(address, address, ERC7984ERC20WrapperHarness.externalEuint64, bytes).selector;

definition isFinalize(method f) returns bool =
    f.selector == sig:finalizeUnwrap(bytes32, uint64, bytes).selector;

/// The eight confidential-transfer entry points: each of the four kinds with and without a memo.
definition isTransferEntry(method f) returns bool =
    f.selector == sig:confidentialTransfer(address, ERC7984ERC20WrapperHarness.externalEuint64, bytes).selector
    || f.selector == sig:confidentialTransfer(address, ERC7984ERC20WrapperHarness.externalEuint64, bytes, bytes32).selector
    || f.selector == sig:confidentialTransferFrom(address, address, ERC7984ERC20WrapperHarness.externalEuint64, bytes).selector
    || f.selector == sig:confidentialTransferFrom(address, address, ERC7984ERC20WrapperHarness.externalEuint64, bytes, bytes32).selector
    || f.selector == sig:confidentialTransferAndCall(address, ERC7984ERC20WrapperHarness.externalEuint64, bytes, bytes).selector
    || f.selector == sig:confidentialTransferAndCall(address, ERC7984ERC20WrapperHarness.externalEuint64, bytes, bytes, bytes32).selector
    || f.selector == sig:confidentialTransferFromAndCall(address, address, ERC7984ERC20WrapperHarness.externalEuint64, bytes, bytes).selector
    || f.selector == sig:confidentialTransferFromAndCall(address, address, ERC7984ERC20WrapperHarness.externalEuint64, bytes, bytes, bytes32).selector;

definition isCallbackWrap(method f) returns bool =
    f.selector == sig:onTransferReceived(address, address, uint256, bytes).selector;
