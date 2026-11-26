// SPDX-License-Identifier: MIT
pragma solidity ^0.8.27;

import {ZamaEthereumConfig} from "@fhevm/solidity/config/ZamaConfig.sol";
import {IERC20} from "@openzeppelin/contracts/interfaces/IERC20.sol";
import {ERC7984} from "../../contracts/token/ERC7984/ERC7984.sol";
import {ERC7984ERC20Wrapper} from "../../contracts/token/ERC7984/extensions/ERC7984ERC20Wrapper.sol";

/// @dev The smallest deployable {ERC7984ERC20Wrapper}: no entry point beyond the library's own. The mock in
/// `contracts/mocks` exposes `$_mint` and `$_burn`, which would let any caller change the supply.
/// Name, symbol and contract URI are empty: no property reads them, and copying strings in the constructor only
/// slows the base case of every invariant.
contract ERC7984ERC20WrapperHarness is ERC7984ERC20Wrapper, ZamaEthereumConfig {
    constructor(IERC20 underlying_) ERC7984ERC20Wrapper(underlying_) ERC7984("", "", "") {}
}
