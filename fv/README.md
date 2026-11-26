# Running formal verification tool

These instructions detail the process for running the Certora Prover on OpenZeppelin Confidential Contracts, and
summarize what the specs verify.

The specs cover `ERC7984ERC20Wrapper`
([contracts/token/ERC7984/extensions/ERC7984ERC20Wrapper.sol](../contracts/token/ERC7984/extensions/ERC7984ERC20Wrapper.sol))
and the `ERC7984` confidential token it extends, at `master` d9927be (2026-11-25). They are a port of the Certora specs
for Zama's `ConfidentialWrapper`, which copies `ERC7984` and `ERC7984ERC20Wrapper` at v0.4.0.
[PORT.md](specs/ERC7984ERC20Wrapper/PORT.md) lists which rules were ported as is, adapted or dropped.

Documentation for the Certora Prover and the specification language is available [here](https://docs.certora.com).

## Prerequisites

Follow the [Certora installation guide](https://docs.certora.com/en/latest/docs/user-guide/getting-started/install.html)
in order to get the Certora Prover Package and the `solc` executable folder in your path. The configurations use
solc 0.8.27 under the name `solc8.27`.

The configurations also read dependencies from `node_modules` and from the `lib/openzeppelin-contracts` submodule.
Install them from the root of the repository:

```bash
npm ci
git submodule update --init lib/openzeppelin-contracts
```

> **Note**
> An API Key is required to run the prover (`CERTORAKEY`). The prover is not run in CI.

## Running the verification

The specs are in `fv/specs/ERC7984ERC20Wrapper/`. Each one is run by a `.conf` file in `fv/confs/` that holds its
pre-configured options:

| Configuration | Spec | What it verifies |
|---|---|---|
| `wrapper_solvency` | `solvency.spec` | Backing and supply |
| `wrapper_wrap` | `wrap.spec` | Wrapping, directly and through the ERC-1363 callback |
| `wrapper_unwrap` | `unwrap.spec` | Unwrap requests and their finalization |
| `wrapper_transfer` | `transfer.spec` | Confidential transfers and operators |
| `wrapper_callback` | `callback.spec` | Transfer-and-call and refunds |
| `wrapper_acl` | `acl.spec` | ACL permissions on encrypted handles |
| `wrapper_params` | `params.spec` | Decimals, rate, underlying and ERC-165 |
| `probe_constructor` | `probe_constructor.spec` | Probes of the constructor (not properties) |

The specs share their models through `fv/specs/ERC7984ERC20Wrapper/setup/`: FHE and ACL (`fhe.spec`), the underlying
token (`underlying.spec`), balance and supply ghosts (`ledger.spec`), a dispatcher over every transfer entry point
(`transfers.spec`) and the invariants that other rules rely on (`invariants.spec`).

Run a configuration from the root of the repository with:

```bash
certoraRun fv/confs/NAME.conf [--rule RULE_NAME]
```

Example usage:

```bash
certoraRun fv/confs/wrapper_solvency.conf # Run every rule of the solvency spec
certoraRun fv/confs/wrapper_unwrap.conf --rule finalizePaysRecordedReceiverOnce # Run a single rule
```

> **Note**
> `advertisesTokenWrapperAndReceiverInterfaces` must be run with `--rule_sanity none`. `supportsInterface` reads no
> state, so the sanity check for a trivial postcondition fails by construction.

The slowest rules take about 7 to 8 minutes each.

## Adapting to changes in the contracts

The contracts are verified unmodified: no patches are applied. The rules run on harness contracts found in the
`fv/harnesses` directory:

- `ERC7984ERC20WrapperHarness.sol` is the smallest deployable `ERC7984ERC20Wrapper`: the wrapper with
  `ZamaEthereumConfig` and empty name, symbol and contract URI. The mock in `contracts/mocks` is not used, because its
  `$_mint` and `$_burn` would let any caller change the supply.
- `WrapperSpecHelper.sol` computes pure values that CVL cannot, such as interface ids and the ERC-1363 data that names a
  recipient.
- `UnderlyingDecimalsMock.sol` is a token with a configurable `decimals()`, used by the probes.

The specs name the wrapper's storage fields and entry points. If those change, update
`setup/ledger.spec` (storage hooks) and `setup/transfers.spec` (transfer entry points) first, and record the new code
version in [PORT.md](specs/ERC7984ERC20Wrapper/PORT.md).

## Results

Results as of 2026-11-26. Each result links to the prover report of the rule's best run.

| | Count |
|---|---|
| Rules and invariants | 63, in 7 configurations |
| Verified | 61, including 3 `satisfy` witnesses that found the scenario |
| Violated | 2, both open questions carried over from the Zama port (see below) |
| Probes (expected VIOLATED, not properties) | 2 |

Every result holds under the assumptions in [ASSUMPTIONS.md](ASSUMPTIONS.md), summarized [below](#assumptions).

- **The wrapper is solvent.** The underlying it holds always covers, at the fixed rate, every confidential token in
  circulation plus every unwrap request not yet finalized. The total supply always equals the sum of balances.
- **Wrap and unwrap move exactly the right amounts.** A wrap takes `x - x mod rate` and credits `floor(x / rate)`. A
  finalization pays `decrypted_amount * rate` once, to the receiver recorded at request time, and only with an
  accepted KMS proof.
- **Transfers conserve value and do not leak information.** A transfer moves the full amount or nothing. It never
  touches an uninvolved balance and never mints or burns. Whether it reverts depends only on public conditions, not on
  encrypted balances or amounts.
- **Permissions on encrypted handles stay correct.** A transfer gives no third party access to either party's
  balance. Stored balance handles stay usable by the wrapper and their holder. Moving or disclosing an existing
  encrypted amount needs the caller's permission.

### Open questions

Both violations reproduce findings of the Zama port. Each rule states one reading of the intended behaviour. The
code does not follow that reading, and it is for OpenZeppelin to say which reading is intended.

#### 1. A transient permission is enough to make an amount publicly decryptable

Rule `transientAllowanceCannotBeEscalatedToPublicDisclosure` (`acl.spec`) is
[VIOLATED](https://prover.certora.com/output/6893/56862ffe3ede4e74ab3fe74f2c46a9d0?anonymousKey=e3313e8688f5576364207123adad93ac5347b093). Zama port findings TOK-11 and
TOK-18.

`confidentialTransferFrom` gives the calling operator a transient permission on the amount it returns.
`requestDiscloseEncryptedAmount` accepts any `FHE.isAllowed` permission, transient ones included. So in the same
transaction an operator can make the transferred amount publicly decryptable, and that cannot be undone. The rule
requires a persistent permission for disclosure.

**Question:** should a transient permission be enough to request public disclosure?

#### 2. Confidential tokens sent to the wrapper's own address are stranded

Rule `transferToTokenContractStrandsCollateral` (`callback.spec`) is
[VIOLATED](https://prover.certora.com/output/6893/3292abf5f57446228346a204f06922d3?anonymousKey=130f18dd9e38adb7410be3eb7578c08995a37ade). Zama port finding TOK-21.

A confidential transfer to `address(this)` succeeds. The wrapper has no way to move its own confidential balance, so
those tokens can never be transferred or unwrapped again, and the underlying that backs them stays locked in the
wrapper.

**Question:** should transfers to the wrapper's own address be rejected?

### Backing and supply (`wrapper_solvency`)

The first five rows are invariants. Other rules rely on them through `requireBooksInvariants()`.

| Rule | Property | Result |
|---|---|---|
| totalSupplyIsSumOfBalances | The confidential total supply equals the sum of all balances. | [Verified](https://prover.certora.com/output/6893/c6a2565baca243ebbfc1a6e4b1c48b67?anonymousKey=a8e4827b6e2dba549316c93c7bd60e6f714f1781) |
| zeroAddressHoldsNothing | The zero address never holds a balance. | [Verified](https://prover.certora.com/output/6893/c6a2565baca243ebbfc1a6e4b1c48b67?anonymousKey=a8e4827b6e2dba549316c93c7bd60e6f714f1781) |
| rateIsPositive | The rate is positive. | [Verified](https://prover.certora.com/output/6893/c6a2565baca243ebbfc1a6e4b1c48b67?anonymousKey=a8e4827b6e2dba549316c93c7bd60e6f714f1781) |
| pendingSumIsNonNegative | The amount held by pending unwrap requests is never negative. | [Verified](https://prover.certora.com/output/6893/c6a2565baca243ebbfc1a6e4b1c48b67?anonymousKey=a8e4827b6e2dba549316c93c7bd60e6f714f1781) |
| wrapperIsSolvent | Underlying held ≥ rate × (supply + pending unwrap amounts). | [Verified](https://prover.certora.com/output/6893/ade22a8dd690414ca376ddbddfec4994?anonymousKey=8faf7dc314e319461894f1fd3275f8a2c75248f1) |
| surplusUnchangedByWrapperOperations | Every operation except the callback wrap leaves the surplus `held - rate * (supply + pending)` unchanged. | [Verified](https://prover.certora.com/output/6893/ade22a8dd690414ca376ddbddfec4994?anonymousKey=8faf7dc314e319461894f1fd3275f8a2c75248f1) |
| callbackWrapConsumesDeliveredAmount | A callback wrap consumes exactly the amount the token delivered. | [Verified](https://prover.certora.com/output/6893/ade22a8dd690414ca376ddbddfec4994?anonymousKey=8faf7dc314e319461894f1fd3275f8a2c75248f1) |
| directTransfersDoNotAffectBooks | Underlying sent directly to the wrapper changes no balance, supply or request. | [Verified](https://prover.certora.com/output/6893/ade22a8dd690414ca376ddbddfec4994?anonymousKey=8faf7dc314e319461894f1fd3275f8a2c75248f1) |
| inferredTotalSupplyIsAtLeastSupply | The public estimate `underlying_held / rate` is at least the actual supply. | [Verified](https://prover.certora.com/output/6893/ade22a8dd690414ca376ddbddfec4994?anonymousKey=8faf7dc314e319461894f1fd3275f8a2c75248f1) |
| supplyMovesOnlyByWrapAndUnwrapRequest | Supply rises only by wrapping and falls only by unwrap requests. | [Verified](https://prover.certora.com/output/6893/ade22a8dd690414ca376ddbddfec4994?anonymousKey=8faf7dc314e319461894f1fd3275f8a2c75248f1) |
| underlyingLeavesOnlyByFinalizeOrRefund | Underlying leaves only by finalization or the callback-wrap remainder refund, at most once per call. | [Verified](https://prover.certora.com/output/6893/ade22a8dd690414ca376ddbddfec4994?anonymousKey=8faf7dc314e319461894f1fd3275f8a2c75248f1) |
| wrapperNeverGrantsAllowance | The wrapper never approves anyone on its underlying. | [Verified](https://prover.certora.com/output/6893/c6a2565baca243ebbfc1a6e4b1c48b67?anonymousKey=a8e4827b6e2dba549316c93c7bd60e6f714f1781) |

### Wrapping (`wrapper_wrap`)

| Rule | Property | Result |
|---|---|---|
| wrapTakesRoundedAmountAndCreditsQuotient | Wrapping `x` takes `x - x mod rate`, credits `floor(x / rate)` and changes no other balance. | [Verified](https://prover.certora.com/output/6893/6ea2ed9f6a8e46d99b7ba49ff4b47747?anonymousKey=5a317c765ea6e7a5672de14d8dd3ca1e8ab6e225) |
| wrapToZeroAddressReverts | A wrap to the zero address reverts. | [Verified](https://prover.certora.com/output/6893/cae6e72efefc4b6e899ffde95d795de7?anonymousKey=f21ae5d30fc7a9f369ceaaaafed2b6096f706f65) |
| wrapRespectsSupplyCap | A wrap never pushes `underlying_held / rate` above the uint64 maximum. | [Verified](https://prover.certora.com/output/6893/cae6e72efefc4b6e899ffde95d795de7?anonymousKey=f21ae5d30fc7a9f369ceaaaafed2b6096f706f65) |
| callbackWrapOnlyFromUnderlying | Only the underlying token can trigger `onTransferReceived`. | [Verified](https://prover.certora.com/output/6893/cae6e72efefc4b6e899ffde95d795de7?anonymousKey=f21ae5d30fc7a9f369ceaaaafed2b6096f706f65) |
| callbackWrapWithEmptyDataCreditsSender | With empty data, the sender is credited and gets the remainder back. | [Verified](https://prover.certora.com/output/6893/6ea2ed9f6a8e46d99b7ba49ff4b47747?anonymousKey=5a317c765ea6e7a5672de14d8dd3ca1e8ab6e225) |
| callbackWrapWithAddressDataCreditsThatAddress | With 20-byte data, that address is credited and the sender gets the remainder. | [Verified](https://prover.certora.com/output/6893/6ea2ed9f6a8e46d99b7ba49ff4b47747?anonymousKey=5a317c765ea6e7a5672de14d8dd3ca1e8ab6e225) |
| callbackWrapWithOtherDataReverts | Data of any other length reverts. | [Verified](https://prover.certora.com/output/6893/cae6e72efefc4b6e899ffde95d795de7?anonymousKey=f21ae5d30fc7a9f369ceaaaafed2b6096f706f65) |
| callbackWrapToZeroRecipientReverts | A callback wrap to the zero address reverts. | [Verified](https://prover.certora.com/output/6893/cae6e72efefc4b6e899ffde95d795de7?anonymousKey=f21ae5d30fc7a9f369ceaaaafed2b6096f706f65) |
| callbackWrapRespectsSupplyCap | A callback wrap never pushes `underlying_held / rate` above the uint64 maximum. | [Verified](https://prover.certora.com/output/6893/cae6e72efefc4b6e899ffde95d795de7?anonymousKey=f21ae5d30fc7a9f369ceaaaafed2b6096f706f65) |

### Unwrapping (`wrapper_unwrap`)

| Rule | Property | Result |
|---|---|---|
| unwrapBurnsAllOrNothingAndRecordsRequest | An unwrap burns exactly `x` or nothing, records the request under a fresh id, makes the burned amount publicly decryptable and moves no underlying. | [Verified](https://prover.certora.com/output/6893/496a6afdc2254fd180a5a4adc0dcaa0c?anonymousKey=db57721f7baac4cdb5ab66fcdfc97c0d5a053a2d) |
| unwrapToZeroReceiverReverts | The receiver cannot be the zero address. | [Verified](https://prover.certora.com/output/6893/214945c55b08424c9ccff8236cf0e638?anonymousKey=e01fc82ecbe36abdefea60946f6835520ea80138) |
| unwrapRequiresHolderOrLiveOperator | Only the holder or an unexpired operator can unwrap. | [Verified](https://prover.certora.com/output/6893/214945c55b08424c9ccff8236cf0e638?anonymousKey=e01fc82ecbe36abdefea60946f6835520ea80138) |
| unwrapWithHandleRequiresCallerAccess | Unwrapping an existing encrypted amount needs the caller's permission on it. | [Verified](https://prover.certora.com/output/6893/214945c55b08424c9ccff8236cf0e638?anonymousKey=e01fc82ecbe36abdefea60946f6835520ea80138) |
| finalizePaysRecordedReceiverOnce | Finalization pays `decrypted * rate` to the recorded receiver and deletes the request. | [Verified](https://prover.certora.com/output/6893/496a6afdc2254fd180a5a4adc0dcaa0c?anonymousKey=db57721f7baac4cdb5ab66fcdfc97c0d5a053a2d) |
| finalizeRequiresAcceptedProof | Finalization reverts without an accepted decryption proof. | [Verified](https://prover.certora.com/output/6893/214945c55b08424c9ccff8236cf0e638?anonymousKey=e01fc82ecbe36abdefea60946f6835520ea80138) |
| finalizeUnknownRequestReverts | Finalizing an unknown request reverts. | [Verified](https://prover.certora.com/output/6893/214945c55b08424c9ccff8236cf0e638?anonymousKey=e01fc82ecbe36abdefea60946f6835520ea80138) |
| finalizeTwiceReverts | A second finalization of the same request reverts. | [Verified](https://prover.certora.com/output/6893/214945c55b08424c9ccff8236cf0e638?anonymousKey=e01fc82ecbe36abdefea60946f6835520ea80138) |
| finalizeOutcomeIndependentOfCaller | The outcome of a finalization does not depend on who calls it. | [Verified](https://prover.certora.com/output/6893/214945c55b08424c9ccff8236cf0e638?anonymousKey=e01fc82ecbe36abdefea60946f6835520ea80138) |
| requestsChangeOnlyByUnwrapAndFinalize | Requests are created only by unwrap and removed only by finalization, and are never overwritten. | [Verified](https://prover.certora.com/output/6893/214945c55b08424c9ccff8236cf0e638?anonymousKey=e01fc82ecbe36abdefea60946f6835520ea80138) |
| pendingRequestIsFinalizable | A pending request with an accepted proof can always be finalized. | [Verified](https://prover.certora.com/output/6893/496a6afdc2254fd180a5a4adc0dcaa0c?anonymousKey=db57721f7baac4cdb5ab66fcdfc97c0d5a053a2d) |

### Confidential transfers (`wrapper_transfer`)

The rules cover all four transfer kinds, each with and without a memo, through the dispatcher in `setup/transfers.spec`.

| Rule | Property | Result |
|---|---|---|
| transferDoesNotDependOnSecrets | Whether a transfer reverts depends only on public conditions, not on balances or the encrypted amount. | [Verified](https://prover.certora.com/output/6893/503a6c4d62624ac7b431abaed9702f98?anonymousKey=06c4b43583cbdc3933867f40e16e7562d6859554) |
| transferFromDoesNotDependOnSecrets | The same for an operator transfer. | [Verified](https://prover.certora.com/output/6893/503a6c4d62624ac7b431abaed9702f98?anonymousKey=06c4b43583cbdc3933867f40e16e7562d6859554) |
| transferConservesValueBetweenParties | The sender loses and the recipient gains exactly the returned amount. | [Verified](https://prover.certora.com/output/6893/503a6c4d62624ac7b431abaed9702f98?anonymousKey=06c4b43583cbdc3933867f40e16e7562d6859554) |
| insufficientBalanceTransfersZero | Asking for more than the balance moves nothing and returns 0. | [Verified](https://prover.certora.com/output/6893/503a6c4d62624ac7b431abaed9702f98?anonymousKey=06c4b43583cbdc3933867f40e16e7562d6859554) |
| sufficientBalanceTransferMovesFullAmount | An affordable request moves the full amount. | [Verified](https://prover.certora.com/output/6893/503a6c4d62624ac7b431abaed9702f98?anonymousKey=06c4b43583cbdc3933867f40e16e7562d6859554) |
| selfTransferIsValuePreserving | A self-transfer leaves the balance unchanged. | [Verified](https://prover.certora.com/output/6893/503a6c4d62624ac7b431abaed9702f98?anonymousKey=06c4b43583cbdc3933867f40e16e7562d6859554) |
| uninvolvedBalancesUnchanged | A transfer writes only the sender's and the recipient's balances. | [Verified](https://prover.certora.com/output/6893/d706598edc4344618b1306ee50c842cf?anonymousKey=c9219a49066dabb92cb22acf9c4924571006b8db) |
| publicTransferEntrypointsCannotMintOrBurn | Transfer entry points reject the zero address on either side and keep the supply unchanged. | [Verified](https://prover.certora.com/output/6893/503a6c4d62624ac7b431abaed9702f98?anonymousKey=06c4b43583cbdc3933867f40e16e7562d6859554) |
| operatorEntriesChangeOnlyByTheirHolder | Only a holder can change its own operator authorizations. | [Verified](https://prover.certora.com/output/6893/d706598edc4344618b1306ee50c842cf?anonymousKey=c9219a49066dabb92cb22acf9c4924571006b8db) |
| setOperatorEffects | `setOperator` reverts exactly for the zero address or the caller itself, and otherwise sets only that entry. | [Verified](https://prover.certora.com/output/6893/d706598edc4344618b1306ee50c842cf?anonymousKey=c9219a49066dabb92cb22acf9c4924571006b8db) |
| balanceDecreasesOnlyThroughHolderOrOperator | A balance decreases only through its holder or an unexpired operator. | [Verified](https://prover.certora.com/output/6893/503a6c4d62624ac7b431abaed9702f98?anonymousKey=06c4b43583cbdc3933867f40e16e7562d6859554) |

### Transfer-and-call (`wrapper_callback`)

| Rule | Property | Result |
|---|---|---|
| andcallRefundBoundedByAmountCredited | The refund is zero or the full amount sent, and the net amount does not underflow. | [Verified](https://prover.certora.com/output/6893/3292abf5f57446228346a204f06922d3?anonymousKey=130f18dd9e38adb7410be3eb7578c08995a37ade) |
| andCallHookAmountIsActuallyTransferred | The receiver hook gets the amount actually moved, not the amount requested. | [Verified](https://prover.certora.com/output/6893/3292abf5f57446228346a204f06922d3?anonymousKey=130f18dd9e38adb7410be3eb7578c08995a37ade) |
| andCallEoaReceiverAcceptsUnconditionally | A recipient without code is not called and keeps the whole amount. | [Verified](https://prover.certora.com/output/6893/3292abf5f57446228346a204f06922d3?anonymousKey=130f18dd9e38adb7410be3eb7578c08995a37ade) |
| receiverAcceptanceSignalFailsClosed | The recipient keeps value only if its answer decrypts to true and it may use that answer. Otherwise the amount is refunded. | [Verified](https://prover.certora.com/output/6893/3292abf5f57446228346a204f06922d3?anonymousKey=130f18dd9e38adb7410be3eb7578c08995a37ade) |
| receiverHookAmountPreauthorizedForReceiver | When the hook runs, the recipient already has permission on the amount and its new balance. | [Verified](https://prover.certora.com/output/6893/3292abf5f57446228346a204f06922d3?anonymousKey=130f18dd9e38adb7410be3eb7578c08995a37ade) |
| transferAndCallToContractCanBeRefunded | Witness: a transfer-and-call can end fully refunded. | [Verified](https://prover.certora.com/output/6893/3292abf5f57446228346a204f06922d3?anonymousKey=130f18dd9e38adb7410be3eb7578c08995a37ade) (witness found) |
| transferAndCallToContractCanBeAccepted | Witness: a transfer-and-call can end with the receiver keeping the amount. | [Verified](https://prover.certora.com/output/6893/3292abf5f57446228346a204f06922d3?anonymousKey=130f18dd9e38adb7410be3eb7578c08995a37ade) (witness found) |
| accountsCanShareBalanceHandle | Witness: two accounts can end with the same balance handle, since handles are deterministic. | [Verified](https://prover.certora.com/output/6893/3292abf5f57446228346a204f06922d3?anonymousKey=130f18dd9e38adb7410be3eb7578c08995a37ade) (witness found) |
| transferToTokenContractStrandsCollateral | No transfer leaves a confidential balance on the wrapper's own address. | **[Violated](https://prover.certora.com/output/6893/3292abf5f57446228346a204f06922d3?anonymousKey=130f18dd9e38adb7410be3eb7578c08995a37ade)**, [open question 2](#2-confidential-tokens-sent-to-the-wrappers-own-address-are-stranded) |

### ACL permissions on encrypted handles (`wrapper_acl`)

| Rule | Property | Result |
|---|---|---|
| storedBalanceHandlesRemainAclAccessible | Every stored balance handle stays usable by the wrapper and by its holder. | [Verified](https://prover.certora.com/output/6893/56862ffe3ede4e74ab3fe74f2c46a9d0?anonymousKey=e3313e8688f5576364207123adad93ac5347b093) |
| storedTotalSupplyHandleRemainsAclAccessible | The total-supply handle stays usable by the wrapper. | [Verified](https://prover.certora.com/output/6893/56862ffe3ede4e74ab3fe74f2c46a9d0?anonymousKey=e3313e8688f5576364207123adad93ac5347b093) |
| transferFromRequiresHolderOrUnexpiredOperator | Transferring for someone else needs an unexpired operator authorization. | [Verified](https://prover.certora.com/output/6893/56862ffe3ede4e74ab3fe74f2c46a9d0?anonymousKey=e3313e8688f5576364207123adad93ac5347b093) |
| handleAmountTransfersRequireCallerAcl | Transferring an existing encrypted amount needs the caller's permission on it. | [Verified](https://prover.certora.com/output/6893/56862ffe3ede4e74ab3fe74f2c46a9d0?anonymousKey=e3313e8688f5576364207123adad93ac5347b093) |
| noCrossAccountBalanceAclGrants | A transfer gives no third party, and neither party, permission on someone else's balance. | [Verified](https://prover.certora.com/output/6893/3c7eaa7c14e34068911df2526d0018fe?anonymousKey=2fa544313734539d299010022395a154b1d3b03a) |
| disclosureRequiresCallerAllowance | Requesting public disclosure needs the caller's permission on the handle. | [Verified](https://prover.certora.com/output/6893/56862ffe3ede4e74ab3fe74f2c46a9d0?anonymousKey=e3313e8688f5576364207123adad93ac5347b093) |
| returnedHandleUsableByCaller | The caller can use the amount handle a transfer returns. | [Verified](https://prover.certora.com/output/6893/56862ffe3ede4e74ab3fe74f2c46a9d0?anonymousKey=e3313e8688f5576364207123adad93ac5347b093) |
| transientAllowanceCannotBeEscalatedToPublicDisclosure | A transient permission is not enough to request public disclosure. | **[Violated](https://prover.certora.com/output/6893/56862ffe3ede4e74ab3fe74f2c46a9d0?anonymousKey=e3313e8688f5576364207123adad93ac5347b093)**, [open question 1](#1-a-transient-permission-is-enough-to-make-an-amount-publicly-decryptable) |

### Token parameters (`wrapper_params`)

| Rule | Property | Result |
|---|---|---|
| constructorDerivesDecimalsAndRate | The constructor gives either rate 1 with at most 6 decimals, or 6 decimals with a power-of-ten rate above 1. | [Verified](https://prover.certora.com/output/6893/ee1ceb719e1248179212d396e015bf88?anonymousKey=d5e7caee49ae5819361043398eb3d578e92d1da4) |
| tokenParametersNeverChange | The underlying, the decimals and the rate never change. | [Verified](https://prover.certora.com/output/6893/ee1ceb719e1248179212d396e015bf88?anonymousKey=d5e7caee49ae5819361043398eb3d578e92d1da4) |
| advertisesTokenWrapperAndReceiverInterfaces | `supportsInterface` is true for ERC-7984, the wrapper, ERC-1363 receiver and ERC-165, and false for `0xffffffff`. | [Verified](https://prover.certora.com/output/6893/474eb454bf3a4336840ec12db7e06f21?anonymousKey=fe5d84c069ae0f295ccfd9d85678fa3522e73b22) |

### Probes (`probe_constructor`)

These are not properties. They show that the constructor can reach both outcomes that
`constructorDerivesDecimalsAndRate` covers: 6 decimals with rate 10^12, and 2 decimals with rate 1. Each invariant
denies one outcome and is expected to be VIOLATED, and both were
([report](https://prover.certora.com/output/6893/f660c0a1c0ba4e00adb64e31bca8ee83?anonymousKey=942d65af69086a456de73d19097f5e02eb508980)). The probe spec has changed since
that run, and the probes have not been re-run on the current version.

## Assumptions

[ASSUMPTIONS.md](ASSUMPTIONS.md) lists every assumption (A1 to A16) with the rules that use it. The main ones:

- **FHE model.** The coprocessor and ACL are summarized in `setup/fhe.spec`. FHE handles are collision-free and
  acyclic. FHE operations never revert: their checks that the caller may use each operand handle are not modelled,
  and every input proof is accepted (A10, A11).
- **KMS.** An accepted decryption proof certifies the true value (A6).
- **Underlying token.** A standard ERC-20: transfers move exactly the nominal amount, with no fee, no rebasing and no
  callback into the wrapper (A13). For `onTransferReceived`, an ERC-1363 token pays before it calls back (A4). The
  wrapper mints without checking that the tokens arrived, so solvency depends on this behaviour of the token.
- **Transfer-and-call receiver.** The hook reverts or returns an answer. It does not reenter and does not spend what it
  received (A12). The best-effort refund that ERC7984 documents, for a receiver that spends the amount and then
  answers false, is not covered.
- **Self-calls.** The wrapper never calls its own entry points, is not its own underlying, and is not the receiver of
  an unwrap request it pays (A2, A3, A5, A7).
- **Prover bounds.** Loops run at most 3 iterations, and hashed data is at most 1024 bytes (A14, A15).
- **Harness.** Name, symbol and contract URI are empty (A16).

Not covered: the features Zama added to its copy (deny-list, pausing, governance, observers and others, see
[PORT.md](specs/ERC7984ERC20Wrapper/PORT.md)), name, symbol and contract URI, and fee-on-transfer or rebasing
underlying tokens, which the wrapper documents as unsupported.
