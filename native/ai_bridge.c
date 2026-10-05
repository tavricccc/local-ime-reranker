/* A tiny Lua module; Rime exports its own Lua API, so no second Lua VM is linked.
 * All network activity is fixed to loopback. One absolute deadline includes
 * connect, send and read. No retry and no child process on the input thread. */
#define WIN32_LEAN_AND_MEAN
#include <winsock2.h>
#include <windows.h>
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <stdio.h>

static double now_ms(void) {
  LARGE_INTEGER count, frequency;
  QueryPerformanceCounter(&count);
  QueryPerformanceFrequency(&frequency);
  return (double)count.QuadPart * 1000.0 / frequency.QuadPart;
}

static int ready(SOCKET socket, int write, double deadline) {
  double remaining = deadline - now_ms();
  if (remaining <= 0) return 0;
  fd_set descriptors;
  FD_ZERO(&descriptors);
  FD_SET(socket, &descriptors);
  fd_set errors = descriptors;
  struct timeval timeout = {(long)(remaining / 1000), (long)((int64_t)(remaining * 1000) % 1000000)};
  return select(0, write ? NULL : &descriptors, write ? &descriptors : NULL, &errors, &timeout) > 0;
}

static void report_exchange(int budget_ms, double started, int received) {
  SOCKET sock = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
  if (sock == INVALID_SOCKET) return;
  u_long nonblocking = 1;
  ioctlsocket(sock, FIONBIO, &nonblocking);
  struct sockaddr_in address = {0};
  address.sin_family = AF_INET;
  address.sin_port = htons(18964);
  address.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
  char message[160];
  int length = snprintf(message, sizeof(message),
                        "{\"elapsed_ms\":%.2f,\"budget_ms\":%d,\"received\":%s}",
                        now_ms() - started, budget_ms, received ? "true" : "false");
  sendto(sock, message, length, 0, (struct sockaddr*)&address, sizeof(address));
  closesocket(sock);
}

__declspec(dllexport) int ai_exchange(const char* payload, int budget_ms, char* output, int capacity) {
  if (budget_ms < 1 || budget_ms > 200 || capacity < 2 || strlen(payload) > 16384) return 0;
  HANDLE signal = OpenEventA(SYNCHRONIZE, FALSE, "Local\\LocalImeRerankerReady");
  if (!signal) return 0;
  int worker_ready = WaitForSingleObject(signal, 0) == WAIT_OBJECT_0;
  CloseHandle(signal);
  if (!worker_ready) return 0;
  double started = now_ms();
  double deadline = started + budget_ms;
  WSADATA data;
  if (WSAStartup(MAKEWORD(2, 2), &data)) return 0;
  SOCKET sock = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
  if (sock == INVALID_SOCKET) { WSACleanup(); return 0; }
  u_long nonblocking = 1;
  ioctlsocket(sock, FIONBIO, &nonblocking);
  struct sockaddr_in address = {0};
  address.sin_family = AF_INET;
  address.sin_port = htons(18963);
  address.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
  int ok = 0;
  if (connect(sock, (struct sockaddr*)&address, sizeof(address)) == SOCKET_ERROR) {
    if (WSAGetLastError() != WSAEWOULDBLOCK || !ready(sock, 1, deadline)) goto done;
    int error = 0, size = sizeof(error);
    getsockopt(sock, SOL_SOCKET, SO_ERROR, (char*)&error, &size);
    if (error) goto done;
  }
  int length = (int)strlen(payload), sent = 0;
  while (sent < length) {
    if (!ready(sock, 1, deadline)) goto done;
    int count = send(sock, payload + sent, length - sent, 0);
    if (count <= 0) goto done;
    sent += count;
  }
  if (!ready(sock, 1, deadline) || send(sock, "\n", 1, 0) != 1) goto done;
  int received = 0;
  while (received < capacity - 1) {
    if (!ready(sock, 0, deadline)) goto done;
    int count = recv(sock, output + received, capacity - received - 1, 0);
    if (count <= 0) goto done;
    received += count;
    char* newline = memchr(output, '\n', received);
    if (newline) { *newline = 0; ok = 1; break; }
  }
done:
  closesocket(sock);
  report_exchange(budget_ms, started, ok);
  WSACleanup();
  return ok;
}

typedef struct lua_State lua_State;
typedef int (*lua_CFunction)(lua_State*);
static const char* (*to_string)(lua_State*, int, size_t*);
static int64_t (*to_integer)(lua_State*, int, int*);
static const char* (*push_string)(lua_State*, const char*, size_t);
static void (*push_nil)(lua_State*);
static void (*create_table)(lua_State*, int, int);
static void (*push_closure)(lua_State*, lua_CFunction, int);
static void (*set_field)(lua_State*, int, const char*);

static int exchange(lua_State* state) {
  size_t length = 0;
  const char* input = to_string(state, 1, &length);
  int budget = (int)to_integer(state, 2, NULL);
  char response[256];
  if (!input || !ai_exchange(input, budget, response, sizeof(response))) push_nil(state);
  else push_string(state, response, strlen(response));
  return 1;
}

__declspec(dllexport) int luaopen_ai_bridge(lua_State* state) {
  HMODULE rime = GetModuleHandleA("rime.dll");
  if (!rime) return 0;
#define LOAD(name, symbol) name = (void*)GetProcAddress(rime, symbol); if (!name) return 0
  LOAD(to_string, "lua_tolstring");
  LOAD(to_integer, "lua_tointegerx");
  LOAD(push_string, "lua_pushlstring");
  LOAD(push_nil, "lua_pushnil");
  LOAD(create_table, "lua_createtable");
  LOAD(push_closure, "lua_pushcclosure");
  LOAD(set_field, "lua_setfield");
  create_table(state, 0, 1);
  push_closure(state, exchange, 0);
  set_field(state, -2, "exchange");
  return 1;
}
