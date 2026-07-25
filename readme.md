# Telegram Username Checker No Rate Limits

Check Telegram usernames via fragment.com API.

## Features

- Checks if a username is taken or available
- Detects user vs channel
- Shows DC (data center)
- Shows avatar status
- Shows premium status
- Checks if Stars, Premium Gift, and Gram are available
- Shows marketplace status (Sold / On auction / Banned / Unavail)
- Shows sale price and purchase date for sold usernames

## Usage

```bash
python3 main.py <username1> [username2 ...]
python3 main.py -f usernames.txt
python3 main.py  # interactive mode
```

### File format (`-f`)

Text file with one username per line. With or without `@`:

```
glebxdlol
xieworld_vf
@dsvsfb42
```

## Example

```bash
python3 main.py glebxdlol xieworld_vf
```

## Author's Contacts

- **Author:** [@glebxdlol](https://t.me/glebxdlol)
- **Channel:** [@xieworld_vf](https://t.me/xieworld_vf)
