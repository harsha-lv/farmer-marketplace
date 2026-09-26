# ADR 0003: Standard Linux Process Isolation Over gVisor Sandboxing

- Status: Accepted
- Deciders: Security Engineering, Platform Infrastructure, ML Engineering
- Date: 2026-09-26

## Context and Problem Statement
Security reviews raised the question of whether to deploy user-space kernel sandboxing (specifically Google gVisor `runsc` or AWS Firecracker microVMs) to isolate the AI quality assay and price forecasting engines.

We analyzed whether the platform's threat model and execution profile warrant hypervisor/user-space kernel interception.

## Decision Drivers
- **Input nature**: The platform processes structured JSON data and binary grain inspection images (JPEG/PNG). It **never** executes untrusted user-submitted scripts, arbitrary binaries, or multi-tenant code.
- **Inference latency & throughput**: Mobile grain quality inspection requires rapid response times (<1.5s per multi-image assay) utilizing optimized CPU vector instructions (AVX-512, NEON) and multi-threaded tensor execution in ONNX Runtime.
- **Operational complexity**: Kernel sandboxes introduce significant operational overhead in standard container orchestration (Kubernetes CNI/CSI compatibility, virtualization requirements).

## Considered Options
1. **gVisor Sandboxing (`runsc`)**: Run the AI assay and price forecasting services inside gVisor containers intercepting all guest system calls.
2. **Standard OCI Container Isolation + Hardened Linux Defense-in-Depth**: Run services in standard OCI containers (`runc`) with non-root users, read-only root filesystems, drop-all capabilities (`CAP_DROP=ALL`), seccomp profiles, and strict memory/CPU limits via cgroups v2.

## Decision Outcome
Chosen option: **Standard OCI Container Isolation + Hardened Linux Defense-in-Depth**.

gVisor sandboxing is **NOT applicable** to this system because:
1. **No arbitrary code execution**: Unlike platforms like Kaggle, JupyterHub, or GitHub Actions, users cannot submit executable code or dynamic scripts. The attack surface is restricted to image decoders and JSON deserializers.
2. **Severe SIMD / Syscall Penalty**: gVisor's Sentry component intercepts POSIX syscalls in user space. Tensor operations and multi-threaded memory mappings (`mmap`, `futex`, threads) in ONNX Runtime and PyTorch suffer a 25%–45% throughput penalty under `runsc`.
3. **Defense-in-Depth at Application Layer**:
   - Pydantic schema validation rejects malformed structures before processing.
   - Multipart file upload validation enforces magic-byte image validation (rejecting non-image payloads).
   - Maximum body size is strictly limited (50 MB via `SecurityMiddleware`).
   - Hardened Docker image: runs as non-root user `appuser:appuser`, read-only rootfs, no capabilities.

### Positive Consequences
- Native hardware acceleration for CPU tensor kernels without virtualization or syscall interception penalties.
- Standard Kubernetes pod deployment without specialized nested virtualization worker nodes.
- Predictable inference latencies under high mandi harvest season load.

### Negative Consequences
- Zero-day vulnerabilities in underlying C/C++ image parsing libraries (e.g. libjpeg, Pillow) must be mitigated via routine container image vulnerability patching.

## Pros and Cons of the Options

### gVisor (`runsc`)
- Good: Strong user-space isolation against zero-day Linux kernel vulnerabilities.
- Bad: 25%–45% degradation in multi-threaded CPU tensor math and memory mapping.
- Bad: Incompatible with GPU acceleration and hardware-accelerated image decoders.
- Bad: Over-engineered for a system that does not run arbitrary untrusted code.

### Hardened Container Isolation (Chosen)
- Good: Full CPU vector performance (AVX-512, SSE, NEON).
- Good: Simple operational model across standard cloud and edge environments.
- Good: Threat model is properly aligned with application risks (image decoding and JSON parsing).
- Bad: Relies on host Linux kernel security boundaries and active patch management.
