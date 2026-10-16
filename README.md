# MiniQubes

MiniQubes is for people who want better compartmentalisation like Qubes OS, without the overhead of running a bunch of virtual machines.

If you're trying to protect yourself from a government with serious resources, go use [Qubes OS](<https://www.qubes-os.org/>). Seriously. MiniQubes is for the average Joe who doesn't like being spied on, wants more control over their system, and wants to make it harder for everything to access everything else.

**Less overhead. Better compartmentalisation. More control over your privacy.**

## What is MiniQubes?

MiniQubes aims to bring the idea of compartmentalisation to everyday users without requiring a full virtualised operating system.

The idea is simple: don't let everything on your system have unrestricted access to everything else.

Instead of going all-in on heavyweight virtual machines, MiniQubes aims to provide a more lightweight approach to separating things that shouldn't necessarily trust each other.

It's for people who care about privacy but don't want to turn their computer into a full-time security research project just to get it.

## Why MiniQubes?

- **Lightweight** — designed to avoid the overhead of running multiple virtual machines.
- **Privacy-focused** — built around the idea of reducing unnecessary access and exposure.
- **Compartmentalisation** — aims to separate different parts of your computing environment.
- **For everyday users** — privacy shouldn't require enterprise hardware or a security degree.
- **Open source** — inspect the code, understand what you're running, and contribute if you want.

## Who is this for?

MiniQubes is for the average person who wants to take their privacy more seriously.

Maybe you don't want every application interacting with everything on your system. Maybe you want to reduce the damage a compromised application could cause. Or maybe you just don't like the idea of giving software unlimited access to your digital life.

Fair enough.

MiniQubes is intended for everyday privacy and security, not as a replacement for a hardened security environment designed to withstand highly capable, targeted attackers.

If you're facing serious targeted threats, look into [Qubes OS](<https://www.qubes-os.org/>) and make sure your entire security setup matches your threat model.

## How to install

### 1\. Clone the repository

Open a terminal and run:

```
git clone https://github.com/133cx-mrkaboom/MiniQubes.git
```

### 2\. Enter the directory

```
cd MiniQubes
```

### 3\. Make the installer executable

```
chmod +x install.sh
```

### 4\. Run the installer

```
./install.sh
```

Follow the instructions provided by the installer.

**Important:** Read through `install.sh` before running it if you want to know exactly what it's going to do. Don't blindly run scripts you haven't checked, especially when they modify your system.

## Security notice

MiniQubes is a security-focused project, but no tool can magically make you anonymous or completely secure.

Your actual security depends on how the software works, how it's configured, your operating system, and the threats you're trying to defend against.

- Keep your system and applications updated.
- Don't run untrusted software just because you think it's isolated.
- Remember that compartmentalisation is only as strong as the mechanisms enforcing it.
- Don't assume MiniQubes provides protection against malware, privilege escalation, or a compromised kernel unless those protections have been implemented and verified.

MiniQubes is not a guaranteed defence against surveillance, and it should not be treated as a substitute for a properly configured security-focused operating system.

## Contributing

Found a bug? Have an idea? Want to improve something?

Contributions are welcome. Feel free to open an issue or submit a pull request.

When reporting a bug, include relevant details such as:

- Your operating system and version.
- The steps needed to reproduce the issue.
- Any relevant error messages or logs.

Please avoid including passwords, private keys, personal information, or other sensitive data in bug reports.

## Disclaimer

MiniQubes is provided as-is, without any guarantee that it will protect you from surveillance, malware, or other security threats.

Understand what you're installing, review the code, and make your own decisions about whether it fits your needs.

## Final words

You shouldn't need a machine packed with virtual machines just to start caring about your privacy.

MiniQubes is about making compartmentalisation more accessible to people who want a little more control over their digital lives.

**Privacy matters. Take control of your own system.**

---

Made for people who don't want to be watched.
