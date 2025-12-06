from solcx import compile_standard, install_solc
import json

install_solc("0.8.20")

with open("Destination.sol", "r") as f:
    destination_source = f.read()

with open("BridgeToken.sol", "r") as f:
    bridge_source = f.read()

compile_input = {
    "language": "Solidity",
    "sources": {
        "Destination.sol": {"content": destination_source},
        "BridgeToken.sol": {"content": bridge_source},
    },
    "settings": {
        "outputSelection": {
            "*": {"*": ["abi", "metadata", "evm.bytecode"]}
        }
    }
}

compiled = compile_standard(compile_input, solc_version="0.8.20")

with open("Destination.json", "w") as f:
    json.dump(
        compiled["contracts"]["Destination.sol"]["Destination"],
        f,
        indent=4
    )

print("✅ Recompiled Destination.sol to Destination.json")