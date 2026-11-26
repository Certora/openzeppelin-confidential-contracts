// SPDX-License-Identifier: MIT
pragma solidity ^0.8.27;

import {IERC1363Receiver} from "@openzeppelin/contracts/interfaces/IERC1363Receiver.sol";
import {IERC165} from "@openzeppelin/contracts/utils/introspection/IERC165.sol";
import {IERC7984} from "../../contracts/interfaces/IERC7984.sol";
import {IERC7984ERC20Wrapper} from "../../contracts/interfaces/IERC7984ERC20Wrapper.sol";

/// @dev Verification-only helper for the ERC7984ERC20Wrapper specs: pure values CVL cannot compute.
/// It holds no state and the wrapper never calls it.
contract WrapperSpecHelper {
    /// @dev ERC-1363 `data` that names `recipient` as the wrap recipient (20-byte encoding).
    function encodeRecipient(address recipient) external pure returns (bytes memory) {
        return abi.encodePacked(recipient);
    }

    function erc7984InterfaceId() external pure returns (bytes4) {
        return type(IERC7984).interfaceId;
    }

    function erc7984ERC20WrapperInterfaceId() external pure returns (bytes4) {
        return type(IERC7984ERC20Wrapper).interfaceId;
    }

    function erc1363ReceiverInterfaceId() external pure returns (bytes4) {
        return type(IERC1363Receiver).interfaceId;
    }

    function erc165InterfaceId() external pure returns (bytes4) {
        return type(IERC165).interfaceId;
    }
}
