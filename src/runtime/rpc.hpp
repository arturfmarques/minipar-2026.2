namespace mp {
constexpr const char* rpc_version="MiniParRPC/1";
using Handler=std::function<std::string(const std::string&)>;
using Registry=std::map<std::string,Handler>;
inline std::string rpc_key(const std::string& function,const std::string& types) { return function+"("+types+")"; }
template<class... Args,class F> Handler bind_rpc(F function) {
    return [function=std::move(function)](const std::string& bytes) {
        Reader input{bytes}; auto arguments=read_arguments<Args...>(input); input.end();
        using R=canonical_t<std::invoke_result_t<F,Args...>>;
        Writer result;
        if constexpr(std::is_void_v<R>) { std::apply(function,arguments); result.string("void"); }
        else { auto value=snapshot(std::apply(function,arguments)); Codec<R>::put(result,value); }
        return result.bytes;
    };
}
inline std::string response(const std::string& program,const std::string& id,bool success,const std::string& body) {
    Writer out;
    out.string(rpc_version); out.string(program); out.string(id); out.string(success?"ok":"error");
    out.string(pid()); out.string(body); return out.bytes;
}
inline void serve_request(Socket client,const std::string& program,const Registry& registry) {
    std::string id;
    try {
        auto bytes=receive_frame(client,deadline(io_timeout()));
        Reader input{bytes};
        if(input.string()!=rpc_version) throw Error("Versao RPC incompativel");
        auto requested_program=input.string(); id=input.string();
        auto function=input.string(), types=input.string(), arguments=input.string(); input.end();
        if(id.empty() || id.size()>128) throw Error("Identificador de tarefa invalido");
        if(requested_program!=program) throw Error("Programa/versao incompativel");
        auto found=registry.find(rpc_key(function,types));
        if(found==registry.end()) throw Error("Funcao/assinatura nao autorizada neste trabalhador");
        active_task=id;
        TaskScope children;
        trace("worker_start",id,function);
        auto result=found->second(arguments); children.finish();
        trace("worker_end",id,function);
        send_frame(client,response(program,id,true,result),deadline(io_timeout()));
        finish_reply(client);
    } catch(const std::exception& error) {
        trace("worker_error",id,error.what());
        try { send_frame(client,response(program,id,false,error.what()),deadline(io_timeout())); finish_reply(client); } catch(...) {}
    } catch(...) {
        try { send_frame(client,response(program,id,false,"Falha desconhecida no trabalhador"),deadline(io_timeout())); finish_reply(client); } catch(...) {}
    }
}
template<class R,class Tuple> R remote_call(const std::string& program,const std::string& function,
                                           const std::string& host,double port,const Tuple& arguments) {
    Writer request;
    request.string(rpc_version); request.string(program); request.string(active_task);
    request.string(function); request.string(tuple_types<Tuple>()); request.string(write_arguments(arguments));
    auto socket=connect_to(host,port_number(port),deadline(setting("MINIPAR_CONNECT_TIMEOUT_MS",3000)));
    auto until=deadline(io_timeout());
    send_frame(socket,request.bytes,until);
    auto bytes=receive_frame(socket,until); Reader input{bytes};
    auto version=input.string(), worker_program=input.string(), id=input.string(), status=input.string();
    auto worker_pid=input.string(), body=input.string(); input.end();
    if(version!=rpc_version || id!=active_task) throw Error("Resposta RPC invalida (versao/task id)");
    if(worker_program!=program) throw Error("Programa/versao do trabalhador incompativel");
    trace("remote_result",id,worker_pid);
    if(status=="error") throw Error("Trabalhador "+worker_pid+": "+body);
    if(status!="ok") throw Error("Estado RPC invalido");
    Reader value{body};
    if constexpr(std::is_void_v<R>) {
        if(value.string()!="void") throw Error("Retorno RPC incompativel com void"); value.end();
    } else {
        auto result=Codec<R>::get(value); value.end(); return result;
    }
}
template<class F,class Tuple> auto fork_remote(const std::string& program,const std::string& function,
                                             F signature,const Tuple& input) {
    auto values=snapshot_tuple(input);
    return [&]<std::size_t... I>(std::index_sequence<I...>) {
        auto arguments=std::tuple{std::get<I+2>(values)...};
        using R=canonical_t<decltype(std::apply(signature,arguments))>;
        // signature só participa da dedução: jamais executa no cliente.
        auto host=std::get<0>(values); auto port=std::get<1>(values);
        return launch_task("remote "+function,[program,function,host,port,arguments=std::move(arguments)]() -> R {
            return remote_call<R>(program,function,host,port,arguments);
        });
    }(std::make_index_sequence<std::tuple_size_v<decltype(values)>-2>{});
}
inline int worker_mode(int argc,char** argv,const std::string& program,const Registry& registry) {
    if(argc<=1) return -1;
    std::string mode=argv[1];
    if(mode=="--manifest") {
        std::cout << "program=" << program << " protocol=" << rpc_version << '\n';
        for(const auto& entry:registry) std::cout << entry.first << '\n';
        return 0;
    }
    if(mode!="--worker") throw Error("Opcao nativa desconhecida: "+mode);
    std::string host="127.0.0.1";
    int port=7000, maximum=0, concurrency=8;
    for(int i=2;i<argc;++i) {
        std::string option=argv[i];
        if(i+1>=argc) throw Error("Opcao exige valor: "+option);
        std::string value=argv[++i];
        if(option=="--host") host=value;
        else {
            std::size_t end=0; long number=std::stol(value,&end);
            if(end!=value.size() || number<0 || number>1000000) throw Error("Valor de opcao invalido");
            if(option=="--port") port=port_number(number,true);
            else if(option=="--max-requests") maximum=static_cast<int>(number);
            else if(option=="--workers" && number>=1 && number<=64) concurrency=static_cast<int>(number);
            else throw Error("Opcao/valor invalido: "+option);
        }
    }
    if(registry.empty()) throw Error("Programa sem funcoes remotas registradas");
    auto listener=listen_on(host,port);
    std::cout << "MINIPAR_WORKER_READY {\"host\":\"" << host << "\",\"port\":" << bound_port(listener)
              << ",\"pid\":" << pid() << ",\"program\":\"" << program << "\"}" << std::endl;
    std::vector<std::future<void>> requests;
    int count=0;
    while(maximum==0 || count<maximum) {
        requests.erase(std::remove_if(requests.begin(),requests.end(),[](auto& request) {
            if(request.wait_for(std::chrono::milliseconds(0))==std::future_status::ready) { request.get(); return true; }
            return false;
        }),requests.end());
        if(requests.size()>=static_cast<std::size_t>(concurrency)) { std::this_thread::sleep_for(std::chrono::milliseconds(2)); continue; }
        try {
            auto client=accept_one(listener,deadline(100)); ++count;
            requests.push_back(std::async(std::launch::async,[client=std::move(client),&program,&registry]() mutable {
                serve_request(std::move(client),program,registry);
            }));
        } catch(const Timeout&) {}
    }
    for(auto& request:requests) request.get();
    return 0;
}
} // namespace mp
