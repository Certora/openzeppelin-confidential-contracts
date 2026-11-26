// SPDX-License-Identifier: MIT
pragma solidity ^0.8.27;

/// @dev Verification-only token used by fv/specs/ERC7984ERC20Wrapper/probe_constructor.spec: `decimals()` returns
/// `value`, or reverts when `reverts` is set. The wrapper's constructor does not reach it: the Prover cannot resolve
/// the constructor's `decimals()` call and havocs its answer, so the mock's fields only name the case a probe is
/// about.
contract UnderlyingDecimalsMock {
    uint8 public value;
    bool public reverts;

    function decimals() external view returns (uint8) {
        require(!reverts, "decimals() reverts");
        return value;
    }
}
