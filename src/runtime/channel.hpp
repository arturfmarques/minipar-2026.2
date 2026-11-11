// Canais são descritores; mensagens trafegam por TCP mesmo no mesmo processo.
namespace mp {
class Inbox {
    Socket listener_;
    std::atomic<bool> stop_{false};
    std::thread thread_;
    std::mutex mutex_;
    std::condition_variable available_;
    std::deque<std::string> messages_;
    std::string failure_;
    void loop() {
        while (!stop_) {
            try {
                auto client=accept_one(listener_,deadline(100));
                auto message=receive_frame(client,deadline(io_timeout()));
                {
                    std::lock_guard lock(mutex_);
                    if (messages_.size()>=4096) throw Error("Fila do canal excedida");
                    messages_.push_back(std::move(message));
                }
                available_.notify_one();
                send_frame(client,"OK",deadline(io_timeout()));
                finish_reply(client);
            } catch (const Timeout&) {
                // Prazo de polling do accept e clientes incompletos não derrubam o listener.
            } catch (const Error& error) {
                trace("channel_error","",error.what());
            }
        }
    }
public:
    explicit Inbox(int port):listener_(listen_on(std::getenv("MINIPAR_CHANNEL_BIND")?std::getenv("MINIPAR_CHANNEL_BIND"):"127.0.0.1",port)),
                             thread_([this]{loop();}) {}
    ~Inbox() { stop_=true; available_.notify_all(); if (thread_.joinable()) thread_.join(); }
    std::string take() {
        std::unique_lock lock(mutex_);
        if (!available_.wait_for(lock,std::chrono::milliseconds(io_timeout()),[this]{return !messages_.empty() || stop_;}))
            throw Timeout("Timeout aguardando mensagem em c_channel");
        if (messages_.empty()) throw Error("Canal encerrado");
        auto result=std::move(messages_.front()); messages_.pop_front(); return result;
    }
};
inline std::shared_ptr<Inbox> inbox(int port) {
    static std::mutex mutex;
    static std::map<int,std::shared_ptr<Inbox>> listeners;
    std::lock_guard lock(mutex);
    auto& listener=listeners[port];
    if (!listener) listener=std::make_shared<Inbox>(port);
    return listener;
}
}
class MiniParChannel {
public:
    std::string ip;
    int port;
    MiniParChannel(std::string host,double value):ip(std::move(host)),port(mp::port_number(value)) { mp::endpoint(ip,port); }
    void sendData(const std::string& message) const {
        auto socket=mp::connect_to(ip,port,mp::deadline(mp::setting("MINIPAR_CONNECT_TIMEOUT_MS",3000)),true);
        auto until=mp::deadline(mp::io_timeout());
        mp::send_frame(socket,message,until);
        if (mp::receive_frame(socket,until)!="OK") throw mp::Error("ACK de canal invalido");
    }
    std::string receiveData() const { return mp::inbox(port)->take(); }
};
