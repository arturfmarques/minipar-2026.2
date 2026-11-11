// Runtime MiniPar TCP: IPv4, enquadramento e prazo total por operação.
#include <algorithm>
#include <atomic>
#include <condition_variable>
#include <cstdint>
#include <deque>
#include <functional>
#include <future>
#include <iomanip>
#include <limits>
#include <map>
#include <mutex>
#include <optional>
#include <stdexcept>
#include <tuple>
#include <unordered_map>
#include <fstream>
#include <utility>
#include <climits>
#ifdef _WIN32
#include <winsock2.h>
#include <ws2tcpip.h>
#include <process.h>
#else
#include <sys/socket.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <fcntl.h>
#include <poll.h>
#include <cerrno>
#endif

namespace mp {
using Clock = std::chrono::steady_clock;
using Deadline = Clock::time_point;
struct Error : std::runtime_error { using std::runtime_error::runtime_error; };
struct Timeout : Error { using Error::Error; };

inline int setting(const char* name, int fallback, int minimum=1, int maximum=600000) {
    auto value = std::getenv(name);
    if (!value || !*value) return fallback;
    try {
        std::size_t end=0;
        long number=std::stol(value, &end);
        if (end!=std::strlen(value) || number<minimum || number>maximum) throw Error("range");
        return static_cast<int>(number);
    } catch (...) { throw Error(std::string("Configuracao invalida: ")+name); }
}
inline Deadline deadline(int milliseconds) { return Clock::now()+std::chrono::milliseconds(milliseconds); }
inline int io_timeout() { return setting("MINIPAR_TIMEOUT_MS",10000); }
inline std::size_t frame_limit() { return setting("MINIPAR_MAX_FRAME_BYTES",16*1024*1024,64,128*1024*1024); }
inline std::string pid() {
#ifdef _WIN32
    return std::to_string(_getpid());
#else
    return std::to_string(getpid());
#endif
}
inline std::mutex& output_mutex() { static std::mutex value; return value; }
inline void trace(const std::string& event, const std::string& id, const std::string& detail="") {
    const char* path=std::getenv("MINIPAR_TRACE");
    if (!path || !*path) return;
    static std::mutex mutex;
    std::lock_guard lock(mutex);
    std::ofstream out(path,std::ios::app);
    auto micros=std::chrono::duration_cast<std::chrono::microseconds>(Clock::now().time_since_epoch()).count();
    // Campos de trace não contêm dados do programa nem comandos executáveis.
    out << event << '\t' << pid() << '\t' << id << '\t' << micros << '\t' << detail << '\n';
}
#ifdef _WIN32
using SocketHandle=SOCKET;
constexpr auto invalid_socket=INVALID_SOCKET;
inline int socket_error() { return WSAGetLastError(); }
inline bool pending(int e) { return e==WSAEWOULDBLOCK || e==WSAEINPROGRESS || e==WSAEINTR; }
inline bool disconnected(int e) { return e==WSAECONNRESET || e==WSAECONNABORTED || e==WSAENOTCONN; }
inline void close_socket(SocketHandle fd) { closesocket(fd); }
#else
using SocketHandle=int;
constexpr auto invalid_socket=-1;
inline int socket_error() { return errno; }
inline bool pending(int e) { return e==EWOULDBLOCK || e==EAGAIN || e==EINPROGRESS || e==EINTR; }
inline bool disconnected(int e) { return e==ECONNRESET || e==ECONNABORTED || e==ENOTCONN; }
inline void close_socket(SocketHandle fd) { close(fd); }
#endif
inline void network_init() {
#ifdef _WIN32
    struct Network {
        Network() { WSADATA data; if (WSAStartup(MAKEWORD(2,2),&data)) throw Error("WSAStartup falhou"); }
        ~Network() { WSACleanup(); }
    };
    static Network network;
#endif
}
class Socket {
    SocketHandle fd_=invalid_socket;
public:
    explicit Socket(SocketHandle fd=invalid_socket):fd_(fd) {}
    Socket(const Socket&)=delete;
    Socket& operator=(const Socket&)=delete;
    Socket(Socket&& other) noexcept:fd_(std::exchange(other.fd_,invalid_socket)) {}
    Socket& operator=(Socket&& other) noexcept {
        if (this!=&other) { reset(); fd_=std::exchange(other.fd_,invalid_socket); }
        return *this;
    }
    ~Socket() { reset(); }
    SocketHandle get() const { return fd_; }
    void reset() { if (fd_!=invalid_socket) { close_socket(fd_); fd_=invalid_socket; } }
};
inline void nonblocking(SocketHandle fd) {
#ifdef _WIN32
    u_long enabled=1;
    if (ioctlsocket(fd,FIONBIO,&enabled)) throw Error("ioctlsocket falhou");
#else
    int flags=fcntl(fd,F_GETFL,0);
    if (flags<0 || fcntl(fd,F_SETFL,flags|O_NONBLOCK)<0) throw Error("fcntl falhou");
#endif
}
inline void ready(SocketHandle fd, bool writing, Deadline until) {
    while (true) {
        auto remaining=std::chrono::duration_cast<std::chrono::milliseconds>(until-Clock::now()).count();
        if (remaining<=0) throw Timeout("Timeout TCP");
        int result;
#ifdef _WIN32
        fd_set descriptors; FD_ZERO(&descriptors); FD_SET(fd,&descriptors);
        fd_set exceptions; FD_ZERO(&exceptions); FD_SET(fd,&exceptions);
        timeval time{static_cast<long>(remaining/1000),static_cast<long>((remaining%1000)*1000)};
        result=select(0,writing?nullptr:&descriptors,writing?&descriptors:nullptr,&exceptions,&time);
#else
        pollfd descriptor{fd,static_cast<short>(writing?POLLOUT:POLLIN),0};
        result=poll(&descriptor,1,static_cast<int>(remaining));
#endif
        if (result>0) return;
        if (result==0) throw Timeout("Timeout TCP");
        if (!pending(socket_error())) throw Error("Espera de socket falhou: "+std::to_string(socket_error()));
    }
}
inline int port_number(double port, bool zero_allowed=false) {
    if (!std::isfinite(port) || std::floor(port)!=port || port<(zero_allowed?0:1) || port>65535)
        throw Error("Porta deve ser inteiro entre 1 e 65535");
    return static_cast<int>(port);
}
inline sockaddr_in endpoint(std::string host, int port) {
    network_init();
    if (host=="localhost") host="127.0.0.1";
    sockaddr_in address{};
    address.sin_family=AF_INET; address.sin_port=htons(static_cast<unsigned short>(port));
    if (inet_pton(AF_INET,host.c_str(),&address.sin_addr)!=1) throw Error("Endereco IPv4 invalido: "+host);
    return address;
}
inline Socket make_socket() {
    network_init();
    Socket socket(::socket(AF_INET,SOCK_STREAM,0));
    if (socket.get()==invalid_socket) throw Error("socket falhou: "+std::to_string(socket_error()));
    nonblocking(socket.get());
    return socket;
}
inline Socket connect_to(const std::string& host, int port, Deadline until, bool retry=false) {
    auto address=endpoint(host,port);
    while (true) {
        try {
            auto socket=make_socket();
            int result=::connect(socket.get(),reinterpret_cast<sockaddr*>(&address),sizeof(address));
            if (result<0) {
                int error=socket_error();
                if (!pending(error)) throw Error("Conexao TCP falhou: "+std::to_string(error));
                ready(socket.get(),true,until);
                int status=0;
#ifdef _WIN32
                int length=sizeof(status);
#else
                socklen_t length=sizeof(status);
#endif
                if (getsockopt(socket.get(),SOL_SOCKET,SO_ERROR,reinterpret_cast<char*>(&status),&length)<0 || status)
                    throw Error("Conexao TCP falhou: "+std::to_string(status));
            }
            return socket;
        } catch (const Timeout&) {
            if (!retry || Clock::now()>=until) throw Timeout("Conexao TCP falhou: timeout para "+host+":"+std::to_string(port));
            std::this_thread::sleep_for(std::chrono::milliseconds(20));
        } catch (const Error&) {
            if (!retry || Clock::now()>=until) throw;
            std::this_thread::sleep_for(std::chrono::milliseconds(20));
        }
    }
}
inline Socket listen_on(const std::string& host, int port) {
    auto address=endpoint(host,port);
    auto socket=make_socket();
    int enabled=1;
#ifdef _WIN32
    if(setsockopt(socket.get(),SOL_SOCKET,SO_EXCLUSIVEADDRUSE,reinterpret_cast<const char*>(&enabled),sizeof(enabled))<0)
        throw Error("Nao foi possivel reservar exclusivamente a porta TCP");
#else
    setsockopt(socket.get(),SOL_SOCKET,SO_REUSEADDR,reinterpret_cast<const char*>(&enabled),sizeof(enabled));
#endif
    if (bind(socket.get(),reinterpret_cast<sockaddr*>(&address),sizeof(address))<0)
        throw Error("bind TCP falhou na porta "+std::to_string(port)+": "+std::to_string(socket_error()));
    if (listen(socket.get(),32)<0) throw Error("listen falhou");
    return socket;
}
inline Socket accept_one(const Socket& listener, Deadline until) {
    while (true) {
        ready(listener.get(),false,until);
        Socket client(accept(listener.get(),nullptr,nullptr));
        if (client.get()!=invalid_socket) { nonblocking(client.get()); return client; }
        if (!pending(socket_error())) throw Error("accept falhou");
    }
}
inline int bound_port(const Socket& listener) {
    sockaddr_in address{};
#ifdef _WIN32
    int size=sizeof(address);
#else
    socklen_t size=sizeof(address);
#endif
    if (getsockname(listener.get(),reinterpret_cast<sockaddr*>(&address),&size)<0) throw Error("getsockname falhou");
    return ntohs(address.sin_port);
}
inline void send_all(const Socket& socket, const char* bytes, std::size_t size, Deadline until) {
    std::size_t offset=0;
    while (offset<size) {
        ready(socket.get(),true,until);
        int flags=0;
#ifndef _WIN32
        flags=MSG_NOSIGNAL;
#endif
        int count=::send(socket.get(),bytes+offset,static_cast<int>(std::min<std::size_t>(size-offset,INT_MAX)),flags);
        if (count>0) offset+=count;
        else if (count==0 || !pending(socket_error())) throw Error("Conexao encerrada durante send");
    }
}
inline void receive_all(const Socket& socket, char* bytes, std::size_t size, Deadline until) {
    std::size_t offset=0;
    while (offset<size) {
        ready(socket.get(),false,until);
        int count=recv(socket.get(),bytes+offset,static_cast<int>(std::min<std::size_t>(size-offset,INT_MAX)),0);
        if (count>0) offset+=count;
        else if (count==0) throw Error("Trabalhador/conexao encerrou antes da mensagem completa");
        else if (!pending(socket_error())) {
            int error=socket_error();
            if(disconnected(error)) throw Error("Trabalhador/conexao encerrou antes da mensagem completa (recv "+std::to_string(error)+")");
            throw Error("recv falhou: "+std::to_string(error));
        }
    }
}
inline void send_frame(const Socket& socket,const std::string& data,Deadline until) {
    if (data.size()>frame_limit()) throw Error("Mensagem excede MINIPAR_MAX_FRAME_BYTES");
    std::uint32_t size=htonl(static_cast<std::uint32_t>(data.size()));
    send_all(socket,reinterpret_cast<const char*>(&size),sizeof(size),until);
    send_all(socket,data.data(),data.size(),until);
}
inline std::string receive_frame(const Socket& socket,Deadline until) {
    std::uint32_t size=0;
    receive_all(socket,reinterpret_cast<char*>(&size),sizeof(size),until);
    size=ntohl(size);
    if (size>frame_limit()) throw Error("Frame excede MINIPAR_MAX_FRAME_BYTES");
    std::string data(size,'\0');
    receive_all(socket,data.data(),size,until);
    return data;
}
inline void finish_reply(const Socket& socket) {
    // O cliente fecha após a resposta. Um encerramento passivo evita reter a
    // porta do listener em TIME_WAIT; clientes não cooperativos têm prazo curto.
    try { char extra; receive_all(socket,&extra,1,deadline(200)); } catch(const Error&) {}
}
} // namespace mp
