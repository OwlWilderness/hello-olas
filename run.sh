apt install pipenv
make new_env && pipenv shell
autonomy init --reset --author valory --remote --ipfs --ipfs-node "/dns/registry.autonolas.tech/tcp/443/https"
autonomy packages sync --update-packages
autonomy fetch valory/hello_world:0.1.0 --local --service --alias hello_world_service; cd hello_world_service
autonomy build-image
touch keys.json
echo '[
  {
    "address": "0xcCf25f4B4BE7df28bb6e10c17832B9e705db6cA5",
    "private_key": "0x44c8e3118f4b71392d494f69ca497c64e06b5ce52034a492b28ff305a854ee5d"
  },
  {
    "address": "0x3AC29433C529A19d667b3a6E5b99F7E6F7EF2cc0",
    "private_key": "0x5df8996877e09d5d8fcbb00d079e2ed3ef450d39aaf579d3a5ce55ae4e084be0"
  },
  {
    "address": "0xf94f91C38F449Efa257f177fA905606b140CA151",
    "private_key": "0xfd786d3406e07c44e19cdb418b2bdfbd2cdb4d35ccee5343a3b0ef4271b4defa"
  },
  {
    "address": "0x005d108f233DE3cFE469213A978C73067E83Ef9a",
    "private_key": "0x1c5755620e58ed8596208d8f28c98f00b8718e0dcf33466dcf76f8a5fa1971e9"
  }
]' > keys.json
export ALL_PARTICIPANTS='["0xcCf25f4B4BE7df28bb6e10c17832B9e705db6cA5", "0x3AC29433C529A19d667b3a6E5b99F7E6F7EF2cc0", "0xf94f91C38F449Efa257f177fA905606b140CA151", "0x005d108f233DE3cFE469213A978C73067E83Ef9a"]'
autonomy deploy build ./keys.json -ltm
autonomy deploy run --build-dir ./abci_build/