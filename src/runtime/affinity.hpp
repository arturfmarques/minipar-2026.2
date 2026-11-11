// core(n) identifica um processador logico do SO, nao um nucleo fisico.
#include <system_error>
#ifdef _WIN32
#include <windows.h>
#elif defined(__linux__)
#include <pthread.h>
#include <sched.h>
#endif

namespace mp {
struct CpuAffinity {
    int id=0;
#ifdef _WIN32
    GROUP_AFFINITY native{};
#elif defined(__linux__)
    cpu_set_t native{};
#endif
};
inline Error affinity_error(const std::string& operation,int code) {
    return Error(operation+" falhou ("+std::to_string(code)+"): "+std::system_category().message(code));
}
inline std::vector<CpuAffinity> process_cpus() {
    std::vector<CpuAffinity> result;
#ifdef _WIN32
    USHORT count=0;
    if (!GetProcessGroupAffinity(GetCurrentProcess(),&count,nullptr) && GetLastError()!=ERROR_INSUFFICIENT_BUFFER)
        throw affinity_error("GetProcessGroupAffinity",GetLastError());
    // Uma mascara de processo nao representa restricoes de todos os grupos.
    if (count!=1) throw Error("Afinidade explicita exige processo em um unico grupo Windows; multiplos grupos nao suportados");
    USHORT group=0;
    if (!GetProcessGroupAffinity(GetCurrentProcess(),&count,&group))
        throw affinity_error("GetProcessGroupAffinity",GetLastError());
    DWORD_PTR allowed=0,system=0;
    if (!GetProcessAffinityMask(GetCurrentProcess(),&allowed,&system))
        throw affinity_error("GetProcessAffinityMask",GetLastError());
    if (!allowed) throw Error("Mascara de processadores do processo indisponivel");
    for (unsigned bit=0;bit<sizeof(DWORD_PTR)*CHAR_BIT;++bit) {
        auto mask=DWORD_PTR(1)<<bit;
        if (allowed&mask) {
            CpuAffinity cpu; cpu.id=int(group)*64+int(bit);
            cpu.native.Group=group; cpu.native.Mask=mask;
            result.push_back(cpu);
        }
    }
#elif defined(__linux__)
    cpu_set_t allowed;
    CPU_ZERO(&allowed);
    // getpid identifica a thread principal: forks aninhados nao herdam apenas
    // a lista reduzida da thread pai que ja tenha recebido afinidade.
    if (sched_getaffinity(getpid(),sizeof(allowed),&allowed)!=0)
        throw affinity_error("sched_getaffinity",errno);
    for (int bit=0;bit<CPU_SETSIZE;++bit) {
        if (CPU_ISSET(bit,&allowed)) {
            CpuAffinity cpu; cpu.id=bit;
            CPU_ZERO(&cpu.native); CPU_SET(bit,&cpu.native);
            result.push_back(cpu);
        }
    }
#else
    throw Error("Afinidade de CPU indisponivel neste sistema operacional");
#endif
    if (result.empty()) throw Error("Nenhum processador permitido ao processo");
    return result;
}
inline std::vector<double> available_cpus() {
    std::vector<double> result;
    for (const auto& cpu:process_cpus()) result.push_back(cpu.id);
    return result;
}
inline double current_cpu() {
#ifdef _WIN32
    PROCESSOR_NUMBER cpu{};
    GetCurrentProcessorNumberEx(&cpu);
    return int(cpu.Group)*64+int(cpu.Number);
#elif defined(__linux__)
    int cpu=sched_getcpu();
    if (cpu<0) throw affinity_error("sched_getcpu",errno);
    return cpu;
#else
    throw Error("Consulta de processador indisponivel neste sistema operacional");
#endif
}
inline CpuAffinity resolve_cpu(double id) {
    if (!std::isfinite(id) || id<0 || id!=std::floor(id) || id>INT_MAX)
        throw Error("core exige identificador inteiro nao negativo de processador logico");
    for (const auto& cpu:process_cpus()) if (cpu.id==id) return cpu;
    throw Error("Processador logico "+std::to_string(static_cast<int>(id))+" nao permitido ao processo");
}
inline void apply_cpu_affinity(const CpuAffinity& cpu) {
#ifdef _WIN32
    if (!SetThreadGroupAffinity(GetCurrentThread(),&cpu.native,nullptr))
        throw affinity_error("SetThreadGroupAffinity",GetLastError());
#elif defined(__linux__)
    int error=pthread_setaffinity_np(pthread_self(),sizeof(cpu.native),&cpu.native);
    if (error) throw affinity_error("pthread_setaffinity_np",error);
#else
    throw Error("Afinidade de CPU indisponivel neste sistema operacional");
#endif
    if (current_cpu()!=cpu.id) throw Error("Processador observado difere da afinidade solicitada");
}
} // namespace mp
