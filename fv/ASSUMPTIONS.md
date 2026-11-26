# Assumptions of the ERC7984ERC20Wrapper specs

Every require in `specs/ERC7984ERC20Wrapper/` that is not the `requireInvariant` of a proved invariant, and every Prover setting or summary that removes behaviour. A result holds only under the assumptions its rule uses. Hypotheses, the requires that state the "if" part of a property (their reason strings start with "the property", "public condition of the property" or "rule hypothesis"), are part of the rule's statement and are not listed here.

Paths are relative to `fv/specs/ERC7984ERC20Wrapper/`. All seven confs in `fv/confs/` import `setup/base.spec`, which carries the FHE, ACL, underlying token, ledger and receiver models, so the model assumptions (A10 to A15) apply to every rule. The rules that call `requireBooksInvariants()` (`setup/invariants.spec`) rely on the proved invariants, whose `preserved` blocks carry A2 and A4 to A6.

## Assumptions

### A1. The zero address sends no transaction

`require e.msg.sender != 0` in transferDoesNotDependOnSecrets (`transfer.spec:26`).

- **Reason.** No key controls address 0, and ERC-7984 rejects it as the sender of a transfer.

### A2. The wrapper never calls its own entry points

`require e.msg.sender != currentContract` in the `preserved` block of wrapperIsSolvent (`setup/invariants.spec:33`) and in surplusUnchangedByWrapperOperations (`solvency.spec:27`), underlyingLeavesOnlyByFinalizeOrRefund (`solvency.spec:120`) and wrapTakesRoundedAmountAndCreditsQuotient (`wrap.spec:17`).

- **Reason.** Neither ERC7984 nor ERC7984ERC20Wrapper makes a `this.f()` call (the overloads without a memo call the memo forms internally). As its own depositor, a wrap would move no underlying, because sender and receiver are the same account, and would still mint.

### A3. The wrapper is not the sender of an ERC-1363 callback

`require from != currentContract` in callbackWrapConsumesDeliveredAmount (`solvency.spec:51`), callbackWrapWithEmptyDataCreditsSender (`wrap.spec:67`) and callbackWrapWithAddressDataCreditsThatAddress (`wrap.spec:95`).

- **Reason.** The wrapper never calls `transferAndCall` on its own underlying, so it never sends the callback that `onTransferReceived` handles.

### A4. The token credits the wrapper before an ERC-1363 callback

`require surplus() >= to_mathint(amount)` in the `onTransferReceived` `preserved` block of wrapperIsSolvent (`setup/invariants.spec:43`).

- **Reason.** A standard ERC-1363 token transfers `amount` before it calls `onTransferReceived`. The wrapper mints without checking that the tokens arrived, so without this assumption an underlying token that calls back without paying makes the wrapper mint unbacked tokens, and wrapperIsSolvent fails.

### A5. The underlying token is not the wrapper

`require underlying() != currentContract` in the `preserved` blocks of wrapperIsSolvent (`setup/invariants.spec:34`, `:38`, `:47`).

- **Reason.** The constructor does not check its `underlying_` argument, so this cannot be an invariant. A wrapper that is its own underlying moves nothing in the real code (its SafeERC20 calls fail), while the ghost balances of the token model would let the calls succeed.

### A6. An accepted KMS proof certifies the decrypted value

`require fheVal(id) == to_mathint(cleartext)` in the `finalizeUnwrap` `preserved` block of wrapperIsSolvent (`setup/invariants.spec:49`) and in surplusUnchangedByWrapperOperations (`solvency.spec:34`), finalizePaysRecordedReceiverOnce (`unwrap.spec:97`) and pendingRequestIsFinalizable (`unwrap.spec:190`). The summary `FHE.checkSignatures => cvlCheckSignatures` (`setup/fhe.spec`) accepts or rejects a proof by the free ghost `kmsAccepts`.

- **Reason.** The KMS signs only the true decryption of a handle, and the Prover cannot check signatures (F5).

### A7. An unwrap request is not paid to the wrapper itself

`require unwrapRequester(id) != currentContract` in surplusUnchangedByWrapperOperations (`solvency.spec:37`) and `require receiver != currentContract` in finalizePaysRecordedReceiverOnce (`unwrap.spec:102`).

- **Reason.** Finalizing such a request pays the wrapper from itself, so nothing is paid out and the burned amount becomes a direct transfer, which these two rules do not describe.

### A8. The underlying token accepts the payout of a finalization

`require !uTokenRejects` and the require that the receiver's balance does not overflow, in pendingRequestIsFinalizable (`unwrap.spec:191`, `:192`).

- **Reason.** A token that refuses the transfer, or a receiver balance that would overflow, makes the finalization revert, as in a standard ERC-20. The rule states that nothing in the wrapper blocks the finalization.

### A9. Input-form calls carry a non-empty input proof

`require proof.length > 0` in andCallHookAmountIsActuallyTransferred (`callback.spec:49`), insufficientBalanceTransfersZero (`transfer.spec:72`), sufficientBalanceTransferMovesFullAmount (`transfer.spec:93`) and the helper `doUnwrap` (`unwrap.spec:20`).

- **Reason.** With a non-empty proof `FHE.fromExternal` verifies the input and yields `verifiedHandle(input)`, which these rules use to name the amount. With an empty proof it uses the input as an existing handle, which handleAmountTransfersRequireCallerAcl (`acl.spec`) and the handle form of `unwrap` cover.

### A10. FHE handles are collision-free and acyclic (F2)

The requires in `trivialHandle`, `cvlFheBin`, `cvlFheSelect`, `cvlTrivial` and `cvlVerify` (`setup/fhe.spec`): a result is never the uninitialized handle, it records the operation and operands that produced it, and it ranks above each operand (`hRank`).

- **Reason.** A handle is a hash of its operation and operands, so equal handles mean equal computations, and a handle cannot be its own ancestor.

### A11. FHE and ACL operations never revert (F4)

The `Impl` summaries of `setup/fhe.spec`.

- **Reason.** The FHE operations are external calls to the coprocessor and the ACL, which the Prover cannot resolve, so they are summarized. Their checks that the caller may use each operand handle are not modelled, and `Impl.verify` accepts every input proof. Rules that assert a call does not revert hold only while the wrapper is allowed on every handle it uses, which storedBalanceHandlesRemainAclAccessible and storedTotalSupplyHandleRemainsAclAccessible (`acl.spec`) state for the stored handles.

### A12. A transfer-and-call receiver either reverts or answers, and changes no state (R1)

Summary `_.onConfidentialTransferReceived => cvlReceiver` (`setup/base.spec`).

- **Reason.** The receiver is an arbitrary contract. In the model it reverts or returns an arbitrary acceptance handle and does not reenter or spend what it received, so the best-effort refund that ERC7984 documents (a receiver that spends the amount in its hook and answers false) is outside every rule.

### A13. The underlying token is a standard ERC-20 (U1, U2)

Summaries of `SafeERC20.safeTransfer`, `SafeERC20.safeTransferFrom`, `_.balanceOf` and `_.approve` (`setup/underlying.spec`).

- **Reason.** The token's code is unknown, so it is modelled: a transfer moves exactly the nominal amount (no fee on transfer, no rebasing), touches no other balance and makes no callback into the wrapper. It may be refused, and it reverts on an insufficient balance or an overflowing credit. Allowances are not modelled. ERC7984ERC20Wrapper documents that fee-on-transfer and deflationary tokens are not supported.

### A14. Loops run at most 3 iterations

All confs: `"optimistic_loop": true`, `"loop_iter": "3"`.

- **Reason.** A Prover limit. The loops in the scene copy `bytes` arguments.

### A15. Hashed data is at most 1024 bytes

All confs: `"optimistic_hashing": true`, `"hashing_length_bound": "1024"`.

- **Reason.** A Prover limit.

### A16. The harness

`fv/harnesses/ERC7984ERC20WrapperHarness.sol` is `ERC7984ERC20Wrapper` with `ZamaEthereumConfig`, as the mock in `contracts/mocks` is, but without the mock's `$_mint`, `$_burn` and other test entry points. Its constructor passes empty strings as name, symbol and contract URI.

- **Reason.** The test entry points would let any caller change the supply. No rule reads the strings, and copying them in the constructor only slows the base case of every invariant. `name()`, `symbol()` and `contractURI()` are views: the parametric rules leave out views, and views cannot break an invariant.

## Not assumptions

- **Proved invariants**, used with `requireInvariant`, proved in `wrapper_solvency.conf`: totalSupplyIsSumOfBalances, zeroAddressHoldsNothing, rateIsPositive, pendingSumIsNonNegative and wrapperIsSolvent (`setup/invariants.spec`). Their `preserved` requires are listed above (A2, A4 to A6).
- **Requires that tie a ghost to storage**: the `Sload` hooks of `setup/ledger.spec`.
- **Requires that bound a term by its sum** (L1, `setup/ledger.spec`): a single non-negative term of a sum never exceeds the sum.
- **Requires that define exact results**: plaintext arithmetic modulo 2^64 and exact comparisons and select (F1), a handle's plaintext is fixed and fits 64 bits (F3), the wrapper verifies one handle per KMS check, and the shape requires of the transfer dispatcher (`setup/transfers.spec`).
- **Pins of rule parameters**: the handle parameters of `acl.spec` name the final balance handles and the returned amount, so the rules cover every handle.
- **Instrumentation starts at its initial value**, as every transaction does: `outCount == 0`, `kmsChecks == 0`.
- **`require e.msg.value == 0`** in the rules that assert a call does not revert, or state exactly when it reverts: every entry point is non-payable, so a non-zero value only adds a revert.
- **The constructor's `decimals()` query.** The Prover cannot resolve this `staticcall` in constructor code and havocs only its return value. That covers every answer of the token, a failure and a malformed reply, so it removes no behaviour; constructorDerivesDecimalsAndRate (`params.spec`) is stated over the outcomes for that reason.
- **`--rule_sanity none` for advertisesTokenWrapperAndReceiverInterfaces.** `supportsInterface` reads no state, so the condition holds in every state and the sanity check for a trivial postcondition fails by construction. Turning it off removes no behaviour.
- **Filters.** Views are left out of rules that look for a state change. `onTransferReceived` is left out of surplusUnchangedByWrapperOperations because callbackWrapConsumesDeliveredAmount states its exact effect.
