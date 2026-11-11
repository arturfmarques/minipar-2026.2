namespace mp {
inline std::string next_task_id() {
    static std::atomic<std::uint64_t> sequence{0};
    static const std::string session=[] {
        std::random_device random;
        return std::to_string((std::uint64_t(random())<<32)^std::uint64_t(random()));
    }();
    return pid()+"-"+session+"-"+std::to_string(++sequence);
}
inline thread_local std::string active_task;
struct PendingTask {
    virtual void wait()=0;
    virtual ~PendingTask()=default;
};
class TaskGroup {
    std::mutex mutex_;
    std::vector<std::shared_ptr<PendingTask>> tasks_;
public:
    void add(std::shared_ptr<PendingTask> task) { std::lock_guard lock(mutex_); tasks_.push_back(std::move(task)); }
    void finish() {
        std::vector<std::shared_ptr<PendingTask>> tasks;
        { std::lock_guard lock(mutex_); tasks=tasks_; }
        std::exception_ptr error;
        for (const auto& task:tasks) {
            try { task->wait(); } catch (...) { if (!error) error=std::current_exception(); }
        }
        if (error) std::rethrow_exception(error);
    }
};
inline thread_local TaskGroup* current_group=nullptr;
class TaskScope {
    TaskGroup group_;
    TaskGroup* previous_=current_group;
public:
    TaskScope() { current_group=&group_; }
    ~TaskScope() { try { group_.finish(); } catch (...) {} current_group=previous_; }
    void finish() { group_.finish(); }
};
template<class R> struct TaskState:PendingTask {
    std::string id;
    std::shared_future<R> future;
    void wait() override { future.get(); }
};
template<class R> class Task {
    std::shared_ptr<TaskState<R>> state_;
public:
    Task()=default;
    explicit Task(std::shared_ptr<TaskState<R>> state):state_(std::move(state)) {}
    const std::string& id() const { if (!state_) throw Error("Identificador de tarefa invalido/nao inicializado"); return state_->id; }
    auto join() const {
        auto task_id=id();
        if (task_id==active_task) throw Error("Tarefa nao pode executar join de si mesma");
        trace("join_begin",task_id);
        if (state_->future.wait_for(std::chrono::milliseconds(setting("MINIPAR_JOIN_TIMEOUT_MS",30000)))!=std::future_status::ready)
            throw Timeout("Join excedeu prazo da tarefa "+task_id);
        if constexpr(std::is_void_v<R>) {
            state_->future.get(); trace("join_end",task_id);
        } else {
            auto result=snapshot(state_->future.get());
            trace("join_end",task_id); return result;
        }
    }
};
template<class F> auto launch_task(const std::string& label,F action,std::optional<CpuAffinity> affinity=std::nullopt) {
    using R=canonical_t<std::invoke_result_t<F>>;
    if (!current_group) throw Error("Fork fora de um contexto de execucao MiniPar");
    auto state=std::make_shared<TaskState<R>>(); state->id=next_task_id();
    auto task_id=state->id;
    trace("spawn",task_id,label);
    state->future=std::async(std::launch::async,[task_id,label,affinity,action=std::move(action)]() mutable -> R {
        active_task=task_id;
        TaskScope children;
        try {
            if (affinity) {
                apply_cpu_affinity(*affinity);
                trace("affinity_applied",task_id,"requested="+std::to_string(affinity->id)+" actual="+std::to_string(static_cast<int>(current_cpu())));
            }
            trace("task_start",task_id,label);
            if constexpr(std::is_void_v<R>) {
                action(); children.finish(); trace("task_end",task_id,label); return;
            } else {
                auto value=action(); children.finish();
                auto result=snapshot(value); trace("task_end",task_id,label); return result;
            }
        } catch(const std::exception& error) {
            trace("task_error",task_id,label);
            throw Error("Tarefa "+task_id+" ("+label+"): "+error.what());
        } catch(...) { trace("task_error",task_id,label); throw Error("Falha desconhecida na tarefa "+task_id); }
    }).share();
    current_group->add(state);
    return Task<R>(std::move(state));
}
template<class F,class Tuple> auto fork_local(const std::string& name,F function,const Tuple& arguments) {
    auto owned=snapshot_tuple(arguments);
    return launch_task(name,[function=std::move(function),owned=std::move(owned)]() mutable {
        return std::apply(function,owned);
    });
}
template<class F,class Tuple> auto fork_local_on(const std::string& name,F function,const Tuple& input) {
    // Argumentos e seletor ja foram avaliados, nessa ordem, na tupla do pai.
    auto values=snapshot_tuple(input);
    constexpr auto size=std::tuple_size_v<decltype(values)>;
    return [&]<std::size_t... I>(std::index_sequence<I...>) {
        auto owned=std::tuple{std::get<I>(values)...};
        auto cpu=resolve_cpu(std::get<size-1>(values));
        return launch_task(name,[function=std::move(function),owned=std::move(owned)]() mutable {
            return std::apply(function,owned);
        },cpu);
    }(std::make_index_sequence<size-1>{});
}
template<class R> auto join(const Task<R>& task) { return task.join(); }
inline void join_all(const std::vector<Task<void>>& tasks) {
    std::exception_ptr error;
    for(const auto& task:tasks) { try { task.join(); } catch(...) { if(!error) error=std::current_exception(); } }
    if(error) std::rethrow_exception(error);
}
}
