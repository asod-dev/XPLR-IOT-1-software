/*
 * Copyright 2020 u-blox
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *  http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

#ifndef _U_SHORT_RANGE_PRIVATE_H_
#define _U_SHORT_RANGE_PRIVATE_H_

/* No #includes allowed here */

/** @file
 * @brief This header file defines types, functions and inclusions that
 * are common and private to the short range API.
 */

#ifdef __cplusplus
extern "C" {
#endif

/* ----------------------------------------------------------------
 * COMPILE-TIME MACROS
 * -------------------------------------------------------------- */

#define U_SHORT_RANGE_UUDPC_TYPE_BT 1
#define U_SHORT_RANGE_UUDPC_TYPE_IPv4 2
#define U_SHORT_RANGE_UUDPC_TYPE_IPv6 3

#define U_SHORT_RANGE_MAX_CONNECTIONS 9

/* ----------------------------------------------------------------
 * TYPES
 * -------------------------------------------------------------- */

typedef enum {
    U_SHORT_RANGE_MODE_COMMAND = 0,
    U_SHORT_RANGE_MODE_DATA = 1,
    U_SHORT_RANGE_MODE_EDM = 2
} uShortRangeModes_t;

/** The characteristics that may differ between short range modules.
 */
//lint -esym(768, uShortRangePrivateModule_t::moduleType) Suppress
//lint -esym(768, uShortRangePrivateModule_t::bootWaitSeconds) Suppress
//lint -esym(768, uShortRangePrivateModule_t::rebootCommandWaitSeconds) Suppress
//lint -esym(768, uShortRangePrivateModule_t::responseMaxWaitMs) Suppress
// may not be referenced as references may be conditionally compiled-out.
typedef struct {
    uShortRangeModuleType_t moduleType; /**< The module type. */
    int32_t bootWaitSeconds; /**< How long to wait before the module is
                                  ready after boot. */
    int32_t rebootCommandWaitSeconds; /**< How long to wait before the module is
                                           ready after it has been commanded
                                           to reboot. */
    int32_t atTimeoutSeconds; /**< The time to wait for completion of an
                                   AT command, i.e. from sending ATblah to
                                   receiving OK or ERROR back. */
    int32_t commandDelayMs; /**< How long to wait between the end of
                                 one AT command and the start of the
                                 next. */
    int32_t responseMaxWaitMs; /**< The maximum response time one can
                                    expect from the short range module.
                                    This is usually quite large since,
                                    if there is a URC about to come
                                    through, it can delay what are
                                    normally immediate responses. */
} uShortRangePrivateModule_t;

typedef struct uShortRangePrivateConnection_t {
    int32_t connHandle;
    uShortRangeConnectionType_t type;
} uShortRangePrivateConnection_t;

/** Definition of a ShortRange instance.
 */
//lint -esym(768, uShortRangePrivateInstance_t::pSpsConnectionCallback) Suppress not reference, it is
//lint -esym(768, uShortRangePrivateInstance_t::pSpsConnectionCallbackParameter) Suppress not reference, it is
//lint -esym(768, uShortRangePrivateInstance_t::pPendingSpsConnectionEvent) Suppress not reference, it is
//lint -esym(768, uShortRangePrivateInstance_t::pBtDataCallback) Suppress not reference, it is
//lint -esym(768, uShortRangePrivateInstance_t::pBtDataCallbackParameter) Suppress not reference, it is
//lint -esym(768, uShortRangePrivateInstance_t::pWifiConnectionStatusCallback) Suppress not reference, it is
//lint -esym(768, uShortRangePrivateInstance_t::pWifiConnectionStatusCallbackParameter) Suppress not reference, it is
//lint -esym(768, uShortRangePrivateInstance_t::pNetworkStatusCallback) Suppress not reference, it is
//lint -esym(768, uShortRangePrivateInstance_t::pNetworkStatusCallbackParameter) Suppress not reference, it is
typedef struct uShortRangePrivateInstance_t {
    int32_t handle; /**< The handle for this instance. */
    int32_t refCounter; /**< Reference counter.
                             Each time uShortRangeAdd() is called with the same atHandle this counter is incremented.
                             When user then call uShortRangeRemove() this counter will be decremented and when it reaches 0
                             the short range instance will be deallocated */
    uShortRangeModes_t mode;
    const uShortRangePrivateModule_t *pModule; /**< Pointer to the module type. */
    uAtClientHandle_t atHandle; /**< The AT client handle to use. */
    int32_t streamHandle; /**< Handle to the underlaying stream. */
    uAtClientStream_t streamType; /**< Stream type. */
    int64_t startTimeMs;     /**< Used while restarting. */
    int64_t ticksLastRestart;
    bool urcConHandlerSet;
    uShortRangePrivateConnection_t connections[U_SHORT_RANGE_MAX_CONNECTIONS];
    uShortRangeBtConnectionStatusCallback_t pBtConnectionStatusCallback;
    void *pBtConnectionStatusCallbackParameter;
    void (*pWifiConnectionStatusCallback) (int32_t, int32_t, int32_t, int32_t, char *, int32_t, void *);
    void *pWifiConnectionStatusCallbackParameter;
    uShortRangeIpConnectionStatusCallback_t pIpConnectionStatusCallback;
    void *pIpConnectionStatusCallbackParameter;
    uShortRangeIpConnectionStatusCallback_t pMqttConnectionStatusCallback;
    void *pMqttConnectionStatusCallbackParameter;
    void (*pNetworkStatusCallback) (int32_t, int32_t, uint32_t, void *);
    void *pNetworkStatusCallbackParameter;
    void (*pSpsConnectionCallback)(int32_t, char *, int32_t, int32_t, int32_t, void *);
    void *pSpsConnectionCallbackParameter;
    void *pPendingSpsConnectionEvent;
    void (*pBtDataCallback) (int32_t, size_t, char *, void *);
//lint -esym(768, uShortRangePrivateInstance_t::pBtDataAvailableCallback)
    void (*pBtDataAvailableCallback)(int32_t, void *);
    void *pBtDataCallbackParameter;
    void (*pDataCallback) (int32_t, size_t, char *, void *);
    void *pDataCallbackParameter;
    char *pBuffer;
    struct uShortRangePrivateInstance_t *pNext;
} uShortRangePrivateInstance_t;

/* ----------------------------------------------------------------
 * VARIABLES
 * -------------------------------------------------------------- */

/** The characteristics of the supported module types, compiled
 * into the driver.
 */
extern const uShortRangePrivateModule_t gUShortRangePrivateModuleList[];

/** Number of items in the gUShortRangePrivateModuleList array.
 */
extern const size_t gUShortRangePrivateModuleListSize;

/** Root for the linked list of instances.
 */
extern uShortRangePrivateInstance_t *gpUShortRangePrivateInstanceList;

/** Mutex to protect the linked list.
 */
extern uPortMutexHandle_t gUShortRangePrivateMutex;

/* ----------------------------------------------------------------
 * FUNCTIONS
 * -------------------------------------------------------------- */

/** Find a short range instance in the list by instance handle.
 * Note: gUShortRangePrivateMutex should be locked before this is called.
 *
 * @param handle  the instance handle.
 * @return        a pointer to the instance.
 */
uShortRangePrivateInstance_t *pUShortRangePrivateGetInstance(int32_t handle);

/** Get whether the given instance is registered with the network.
 * Note: gUShortRangePrivateMutex should be locked before this is called.
 *
 * @param pInstance  a pointer to the ShortRange instance.
 * @return           true if it is registered, else false.
 */
//lint -esym(714, uShortRangePrivateIsRegistered) Suppress lack of a reference
//lint -esym(759, uShortRangePrivateIsRegistered) etc. since use of this function
//lint -esym(765, uShortRangePrivateIsRegistered) may be compiled-out in various ways
//lint -esym(757, uShortRangePrivateIsRegistered)
bool uShortRangePrivateIsRegistered(const uShortRangePrivateInstance_t *pInstance);

/** Get the module characteristics for a given instance.
 *
 * @param handle  the instance handle.
 * @return        a pointer to the module characteristics.
 */
//lint -esym(714, pUShortRangePrivateGetModule) Suppress lack of a reference
//lint -esym(759, pUShortRangePrivateGetModule) etc. since use of this function
//lint -esym(765, pUShortRangePrivateGetModule) may be compiled-out in various ways
const uShortRangePrivateModule_t *pUShortRangePrivateGetModule(int32_t handle);

#ifdef __cplusplus
}
#endif

#endif // _U_SHORT_RANGE_PRIVATE_H_

// End of file
