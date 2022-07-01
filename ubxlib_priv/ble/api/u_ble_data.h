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

#ifndef _U_BLE_DATA_H_
#define _U_BLE_DATA_H_

/* No #includes allowed here */

/** @file
 * @brief This header file defines the APIs that obtain data transfer
 * related commands for ble using the sps protocol.
 */

#ifdef __cplusplus
extern "C" {
#endif

/* ----------------------------------------------------------------
 * COMPILE-TIME MACROS
 * -------------------------------------------------------------- */
/** Invalid connection handle
 */
#define U_BLE_DATA_INVALID_HANDLE ((int32_t)(-1))

/** Size of receive buffer for a connected data channel
 *  When this buffer is full flow control will be invoked
 *  to stop the data flow from remote device, if enabled.
 */
#ifndef U_BLE_DATA_BUFFER_SIZE
#define U_BLE_DATA_BUFFER_SIZE 1024
#endif

/** Maximum number of simultaneous connections,
 *  server and client combined
 */
#ifndef U_BLE_DATA_MAX_CONNECTIONS
#define U_BLE_DATA_MAX_CONNECTIONS 8
#endif

/** Default timeout for data sending. Can be modified per
 *  connection with uBleDataSetSendTimeout.
 */
#ifndef U_BLE_DATA_DEFAULT_SEND_TIMEOUT_MS
#define U_BLE_DATA_DEFAULT_SEND_TIMEOUT_MS 100
#endif

/* ----------------------------------------------------------------
 * TYPES
 * -------------------------------------------------------------- */

/** SPS connection status
 */
typedef enum {
    U_BLE_SPS_CONNECTED = 0,
    U_BLE_SPS_DISCONNECTED = 1,
} uBleConnectionStatus_t;

/** GATT Service handles for SPS server
 */
typedef struct {
    uint16_t     service;
    uint16_t     fifoValue;
    uint16_t     fifoCcc;
    uint16_t     creditsValue;
    uint16_t     creditsCcc;
} uBleDataSpsHandles_t;

/** Connection status callback type
 *
 * @param connHandle         Connection handle (use to send disconnect)
 * @param address            Address
 * @param status             New status of connection, of uBleConnectionStatus_t type
 * @param channel            Channel nbr, use to send data
 * @param mtu                Max size of each packet
 * @param pCallbackParameter Parameter pointer set when registering callback
 */
typedef void (*uBleDataConnectionStatusCallback_t)(int32_t connHandle, char *address,
                                                   int32_t status, int32_t channel, int32_t mtu,
                                                   void *pCallbackParameter);

/** Data callback type
 *
 *  Called to indicate that data is available for reading
 *
 * @param connHandle         Channel number
 * @param pCallbackParameter Parameter pointer set when registering callback
 */
typedef void (*uBleDataAvailableCallback_t)(int32_t channel, void *pCallbackParameter);

/* ----------------------------------------------------------------
 * FUNCTIONS
 * -------------------------------------------------------------- */

/** Sets the callback for connection events
 * When a connected callback arrives, it is advisable to have a 50 ms delay
 * before data is sent on the connect.
 *
 * @param bleHandle          the handle of the ble instance.
 * @param pCallback          callback function. Use NULL to deregister the callback
 * @param pCallbackParameter parameter included with the callback.
 * @return                   zero on success, on failure negative error code.
 */
int32_t uBleDataSetCallbackConnectionStatus(int32_t bleHandle,
                                            uBleDataConnectionStatusCallback_t pCallback,
                                            void *pCallbackParameter);

/** DEPRECATED, use uBleDataSetDataAvailableCallback and uBleDataReceive instead
 *
 * Sets the callback for data events
 *
 * @param bleHandle   the handle of the ble instance.
 * @param pCallback   callback function. Use NULL to deregister the
 *                    callback. Parameter order:
 *                    - channel
 *                    - size
 *                    - data
 *                    - pCallbackParameter
 * @param pCallbackParameter parameter included with the callback.
 * @return            zero on success, on failure negative error code.
 */
__attribute__((deprecated))
int32_t uBleDataSetCallbackData(int32_t bleHandle,
                                void (*pCallback) (int32_t, size_t, char *, void *),
                                void *pCallbackParameter);

/** Sets the callback for data available
 *
 * @param bleHandle          The handle of the ble instance.
 * @param pCallback          Callback function. Use NULL to deregister the callback
 * @param pCallbackParameter Parameter included with the callback.
 * @return                   Zero on success, on failure negative error code.
 */
int32_t uBleDataSetDataAvailableCallback(int32_t bleHandle,
                                         uBleDataAvailableCallback_t pCallback,
                                         void *pCallbackParameter);

/** Create a SPS connection over BLE, this is the u-blox proprietary protocol for
 *  streaming data over ble. Flow control is used.
 *
 * @note If the initiating side is peripheral it must also run a
 *       SPS server which the central device then will connect to when
 *       this function is called.
 *
 * @param bleHandle   the handle of the ble instance.
 * @param pAddress    pointer to the address in 0012F398DD12p format,
 *                    must not be NULL.
 * @return            zero on success, on failure negative error code.
 */
int32_t uBleDataConnectSps(int32_t bleHandle, const char *pAddress);

/** Disconnect the connection.
 * If data has been sent, it is advisable to have a 50 ms delay
 * before calling disconnect.
 *
 * @param bleHandle   the handle of the ble instance.
 * @param connHandle  the connection handle from the connected event.
 * @return            zero on success, on failure negative error code.
 */
int32_t uBleDataDisconnect(int32_t bleHandle, int32_t connHandle);

/**
 *
 * @param bleHandle   The handle of the BLE instance.
 * @param channel     Channel to receive on, given in connection callback
 * @param pData       Pointer to the data buffer, must not be NULL
 * @param length      Size of receive buffer
 *
 * @return            Number of bytes received, zero if no data is available,
 *                    on failure negative error code
 */
int32_t uBleDataReceive(int32_t bleHandle, int32_t channel, char *pData, int32_t length);

/** Send data
 *
 * @param bleHandle   the handle of the ble instance.
 * @param channel     the channel to send on.
 * @param pData       pointer to the data, must not be NULL.
 * @param length      length of data to send, must not be 0.
 * @return            zero on success, on failure negative error code.
 */
int32_t uBleDataSend(int32_t bleHandle, int32_t channel, const char *pData, int32_t length);

/** Set timeout for data sending
 *
 * If sending of data takes more than this time uBleDataSend will stop sending data
 * and return. No error code will be given since uBleDataSend returns the number of bytes
 * actually written.
 *
 * @note This setting is per channel and thus has to be set after connecting.
 *        U_BLE_DATA_DEFAULT_SEND_TIMEOUT_MS will be used if timeout is not set
 *
 * @param bleHandle   The handle of the ble instance.
 * @param channel     The channel to use this timeout on
 * @param timeout     Timeout in ms
 *
 * @return            zero on success, on failure negative error code.
 */
int32_t uBleDataSetSendTimeout(int32_t bleHandle, int32_t channel, uint32_t timeout);

/** Get server handles for channel connection
 *
 * By reading the server handles for a connection
 * and preseting them before connecting to the same server next time,
 * the connection setup speed will improve significantly.
 * Read the server handles for a current connection using this function
 * and cache them for e.g. a bonded device for future use.
 *
 * @note This only works when the connecting side is central.
 *       If connecting side is peripheral it is up to the central
 *       device to cache server handles.
 *
 * @param bleHandle   The handle of the ble instance.
 * @param channel     The channel to read server handles on
 * @param pHandles    Pointer to struct with handles to write
 *
 * @return            zero on success, on failure negative error code.
 */
int32_t uBleDataGetSpsServerHandles(int32_t bleHandle, int32_t channel,
                                    uBleDataSpsHandles_t *pHandles);

/** Preset server handles before conneting
 *
 * By reading the server handles for a connection
 * and preseting them before connecting to the same server next time,
 * the connection setup speed will improve significantly.
 * Preset cached server handles for a bonded device using this function
 * The preset values will be used on the next call to uBleDataConnectSps
 *
 * @note This only works when the connecting side is central.
 *       If connecting side is peripheral it is up to the central
 *       device to cache server handles.
 *
 * @param bleHandle   The handle of the ble instance.
 * @param pHandles    Pointer to struct with handles
 *
 * @return            zero on success, on failure negative error code.
 */
int32_t uBleDataPresetSpsServerHandles(int32_t bleHandle, const uBleDataSpsHandles_t *pHandles);

/** Disable flow control for next SPS connection
 *
 * Flow control is enabled by default
 * Flow control can't be altered for an ongoing connection
 * Disabling flow control decrease connection setup time and data overhead
 * with the risk of loosing data. If the received amount of data during a
 * connection is smaller than U_BLE_DATA_BUFFER_SIZE there is no risk of
 * loosing received data. The risk of loosing sent data depends on remote
 * side buffers.
 *
 * Notice: If you use uBleDataGetSpsServerHandles to read server handles you have
 *         to connect with flow control enabled since some of the server handles
 *         are related to flow control.
 *
 * @param bleHandle   The handle of the ble instance.
 *
 * @return            zero on success, on failure negative error code.
 */
int32_t uBleDataDisableFlowCtrlOnNext(int32_t bleHandle);


#ifdef __cplusplus
}
#endif

#endif // _U_BLE_DATA_H_

// End of file
